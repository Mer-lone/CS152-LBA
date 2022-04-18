from flask import Flask, render_template, request,  redirect, url_for

# taken from https://github.com/yuce/pyswip/issues/3
# pyswip has a problem of threading when using flask
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

prolog.consult("KB.pl")

app = Flask(__name__)

# get csv file with recipes to create the menu options
recipes_df = pd.read_csv("recipes.csv")

# transform the columns into lists
recipes_df["ingredients_names"] = recipes_df["ingredients_names"].apply(eval)
recipes_df["diets"] = recipes_df["diets"].apply(eval)
recipes_df["cuisines"] = recipes_df["cuisines"].apply(eval)
recipes_df["dishTypes"] = recipes_df["dishTypes"].apply(eval)

# create list for menu, some options can be none
ingredients = []
diets = ['none']
cuisines = ['none']
dishTypes = ['none']

# collect all possible values for each
for index, row in recipes_df.iterrows():
    ingredients.extend(row['ingredients_names'])
    diets.extend(row['diets'])
    cuisines.extend(row['cuisines'])
    dishTypes.extend(row['dishTypes'])
    
# transform into a set as we want unique options
ingredients = set(ingredients)
diets = set(diets)
cuisines = set(cuisines)
dishTypes = set(dishTypes)

# alphabetical order
ingredients = list(ingredients)
diets = list(diets)
cuisines = list(cuisines)
dishTypes = list(dishTypes)

ingredients.sort()
diets.sort()
cuisines.sort()
dishTypes.sort()


def get_question():
    """
    This function does a query on the recipes based on the current state of the KB.
    With the Prolog threading problem, it was not possible to use registerForeign
    and so a new strategy was used with a new predicate called question that has a page.
    It returns the first question on the KB. If no questions, return the results page
    with the recipes as parameters. 
    """
    # remove all questions previously
    prolog.retractall("question(_)")
    # query recipes
    recipes = []
    for soln in prolog.query("recipe(Id, Title, Url)"):
        recipe = {"id":soln["Id"], "title":soln["Title"].decode(), "url":soln["Url"].decode()}
        recipes.append(recipe)
    # query questions
    questions = [s for s in prolog.query("question(P).", maxresult= 1)]

    if not questions:
        return "results.html", recipes
    return questions[0]['P'], recipes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start')
def start():
    # when starting we remove any known askable
    prolog.retractall("known(_,_,_)")

    page, recipes = get_question()

    # all pages get the same parameters
    return render_template(page, recipes = recipes, ingredients = ingredients, diets = diets, cuisines = cuisines, dishtypes = dishTypes)

@app.route('/store/<askable>/<value>', methods = ['GET'])
def store(askable,value):
    # when the user answers, we assert the new knowledge on the KB
    prolog.assertz("known(yes, " + askable + ", " + value + ")")

    page, recipes = get_question()

    return render_template(page, recipes = recipes, ingredients = ingredients, diets = diets, cuisines = cuisines, dishtypes = dishTypes)

@app.route('/store/<type>', methods = ['POST'])
def store_post(type):
    askable = request.form['askable']
    # depending on the type of askable we get the value differently
    if type == "list":
        value_list = request.form.getlist('value[]')
        value = "["+", ".join(f"'{w}'" for w in value_list)+"]"
    elif type == "text":
        value = request.form['value']
        value = "'"+str(value)+"'"
    else:
        value = request.form['value']

    # assert new knowledge
    prolog.assertz("known(yes, " + askable + ", " + value + ")")

    page, recipes = get_question()

    return render_template(page, recipes = recipes, ingredients = ingredients, diets = diets, cuisines = cuisines, dishtypes = dishTypes)

if __name__ == '__main__':
    app.run(debug=True)