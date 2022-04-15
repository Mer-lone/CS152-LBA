from flask import Flask, render_template, request,  redirect, url_for

import pyswip, ctypes
import pandas as pd

# taken from https://github.com/yuce/pyswip/issues/3
# pyswip has a problem of threading when using flask
class PrologMT(pyswip.Prolog):
    """Multi-threaded (one-to-one) pyswip.Prolog ad-hoc reimpl"""
    _swipl = pyswip.core._lib

    PL_thread_self = _swipl.PL_thread_self
    PL_thread_self.restype = ctypes.c_int

    PL_thread_attach_engine = _swipl.PL_thread_attach_engine
    PL_thread_attach_engine.argtypes = [ctypes.c_void_p]
    PL_thread_attach_engine.restype = ctypes.c_int

    @classmethod
    def _init_prolog_thread(cls):
        pengine_id = cls.PL_thread_self()
        if (pengine_id == -1):
            pengine_id = cls.PL_thread_attach_engine(None)
            print("{INFO} attach pengine to thread: %d" % pengine_id)
        if (pengine_id == -1):
            raise pyswip.prolog.PrologError("Unable to attach new Prolog engine to the thread")
        elif (pengine_id == -2):
            print("{WARN} Single-threaded swipl build, beware!")

    class _QueryWrapper(pyswip.Prolog._QueryWrapper):
        def __call__(self, *args, **kwargs):
            PrologMT._init_prolog_thread()
            return super().__call__(*args, **kwargs)

prolog = PrologMT()

prolog.assertz("ingredient(X,Y):- false")
prolog.assertz("greater_than(X, Y) :- X @> Y")

recipes_df = pd.read_csv("recipes.csv")

def clean_alt_list(list_):
    list_ = list_.replace('\"', '\'')
    return list_

recipes_df["title"] = recipes_df["title"].apply(clean_alt_list)

recipes_df["ingredients_ids"] = recipes_df["ingredients_ids"].apply(eval)
recipes_df["ingredients_names"] = recipes_df["ingredients_names"].apply(eval)


ingredients = {}

for index, row in recipes_df.iterrows():
    line = "recipe(" + str(row["id"]) + ",\"" + str(row["title"]) + "\",\"" + str(row["url"]) + "\"," + str(row["minutes"]) + "," +str(row["calories"])+"):-"
    
    line += "time(X), greater_than(X, "+str(row["minutes"])+"),"
    line += "calories(Y), greater_than(Y, "+str(row["calories"])+"),"
                                                
    for i in range(len(row["ingredients_ids"])):
        ingredients[row["ingredients_ids"][i]] = str(row["ingredients_names"][i])
        line += "ingredient("+ str(row["ingredients_ids"][i]) + ")"
        if i < len(row["ingredients_ids"]) - 1:
            line += ", "
            
    prolog.assertz(line)

app = Flask(__name__)

@app.route('/')
def index():
    prolog.query("retractall(ingredient(_))")
    prolog.query("retractall(time(_))")
    prolog.query("retractall(calories(_))")
    return render_template('search_recipes.html', ingredients = ingredients)

@app.route('/results', methods = ['POST'])
def results():
    available_ingredients = request.form.getlist('ingredients[]')
    time = request.form['time']
    calories = request.form['calories']

    prolog.assertz('time('+ time +')')
    prolog.assertz('calories('+ calories +')')

    for ing in available_ingredients:
        prolog.assertz('ingredient(' + ing + ')')

    recipes = []
    for soln in prolog.query("recipe(X,Y,Z,K,L)"):
        recipe = {"id":soln["X"], "title":soln["Y"], "url":soln["Z"], "minutes":soln["K"], "calories":soln["L"]}
        recipes.append(recipe)

    return render_template('result_recipes.html', recipes = recipes)

if __name__ == '__main__':
    app.run(debug=True)