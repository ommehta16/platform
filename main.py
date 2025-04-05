# https://flask.palletsprojects.com/en/stable/quickstart/

import grader
import json
import os
import random
import time
import markdown
import uuid
import hashlib
import glob
import string
import pickle
from datetime import datetime
import traceback
from flask import Flask, request, render_template, redirect, abort
app = Flask(__name__)

DEBUG = True
max_testcases:int = 10
games = []
users = []
adminPass = "a" #open("SECRET.txt", "r").read().rstrip() #''.join(random.choice(string.ascii_lowercase) for i in range(40))

# PROBLEM CREATION/EDITING/SOLUTION GRADING
def sortByDifficulty(x):
    # comparator used to sort problems in increasing difficulty
    mapping = {
        "trivial": 0, "easy": 1, "medium": 2, "hard": 3, "very hard": 4
    }
    if "difficulty" in x and x["difficulty"].lower() in mapping:
        return mapping[x["difficulty"].lower()]
    return 5

def get_problem_names():
    # Get all problems, in sorted order
    problem_names = os.listdir("problems")
    problems = []
    for p in problem_names:
        if not ".json" in p:
            continue
        prob = json.load(open("problems/" + p, encoding='utf-8'))
        prob["id"] = p.split(".")[0]
        new_prob = {
            "id": prob["id"],
            "status": prob["status"],
            "title": prob["title"],
        }
        if "difficulty" in prob and prob["difficulty"] != "":
            new_prob["difficulty"] = prob["difficulty"]
        if "tags" in prob and prob["tags"] != "":
            new_prob["tags"] = prob["tags"]
        problems.append(new_prob)
    problems.sort(key = lambda x: x["title"])
    problems.sort(key = sortByDifficulty)
    return problems

def admin_check(req):
    if DEBUG: return True
    return req.cookies.get("userid") == adminPass

@app.route("/list", methods=["GET","POST"])
def catalogue():
    if admin_check(request):
        return render_template("list.html", problems = get_problem_names())
    abort(401)

@app.route("/public", methods=["GET","POST"])
def public_catalogue():
    return render_template("list_public.html", problems = get_problem_names())

@app.route("/upload", methods=["GET", "POST"])
def upload():
    # ensure only admin can access this page
    if not admin_check(request):
        abort(401)

    if request.method == "POST":
        id = request.form["id"]
        title = request.form["title"]
        status = request.form["status"]
        #description = markdown.markdown(request.form["description"])
        description = request.form["description"]
        testcases = []
        for i in range(max_testcases):
            inp = request.form["input" + str(i)]
            out = request.form["output" + str(i)]
            # check if empty
            if inp.rstrip() != "" and out.rstrip() != "":
                testcases.append([inp, out])
        open("problems/" + id + ".json", "w", encoding='utf-8').write(
            json.dumps({
                "title": title,
                "status": status,
                "difficulty": request.form["difficulty"],
                "tags": request.form["tags"],
                "description": description,
                "testcases": testcases
            })
        )
        return redirect("/")
    return render_template("create.html", max_testcases=max_testcases)

@app.route("/edit", methods=["GET", "POST"])
def edit():
    if not admin_check(request):
        abort(401)
    p = request.args.get("id")
    with open("problems/" + p + ".json", encoding='utf-8') as f:
        data = json.load(f)
    data["id"] = p
    if request.method == "POST":
        id = request.form["id"]
        title = request.form["title"]
        status = request.form["status"]
        description = request.form["description"]
        testcases = []
        for i in range(max_testcases):
            inp = request.form["input" + str(i)]
            out = request.form["output" + str(i)]
            # check if empty
            if inp.rstrip() != "" and out.rstrip() != "":
                testcases.append([inp, out])
        open("problems/" + id + ".json", "w", encoding='utf-8').write(json.dumps({
            "title": title,
            "status": status,
            "difficulty": request.form["difficulty"],
            "tags": request.form["tags"],
            "description": description,
            "testcases": testcases
        }))
        return redirect("/list")
    return render_template("edit.html", max_testcases=max_testcases, data=data)

@app.route('/problem', methods=["GET", "POST"])
def problem():
    # Get problem id
    p = request.args.get("id")

    # Load problem description + convert to html
    try:
        with open("problems/" + p + ".json", encoding='utf-8') as f:
            data = json.load(f)
            data["description"] = markdown.markdown(data["description"], extensions=['fenced_code'])
    except:
        abort(404)

    # Run grader if problem is submitted
    if request.method == "POST":
        file = request.files['file']
        print(f"received problem submission for {p}:", file.filename)
        now = datetime.now()
        date = now.strftime("%m-%d-%Y-%H-%M-%S-")

        rand = random_id()
        os.mkdir("tmp/" + date + rand)

        fname = "tmp/" + date + rand + "/" + file.filename
        file.save(fname)
        lang = request.form["language"]

        results = grader.grade(fname, data["testcases"], lang)

        num_ac = 0
        for res in results:
            if res[0] == "AC":
                num_ac += 1

        # give points to player if playing a game
        g_id = request.args.get("g_id")
        p_id = request.args.get("player")
        if (g_id != None) and (p_id != None):
            print("giving score to", p_id, "from game", g_id)
            for game in games:
                if game.id == g_id:
                    for pl in game.players:
                        if pl[0] == p_id:
                            if num_ac == len(results):
                                num_points = 100
                            elif num_ac > 1:
                                num_points = 100 * (num_ac - 1)/(len(results) - 1)
                            else:
                                num_points = -0.0001
                            game.give_points(p_id, p, num_points)
                            pl[3][p] = results
        return render_template("problem.html", results=results, data=data)
    g_id = request.args.get("g_id")
    p_id = request.args.get("player")
    if (g_id != None) and (p_id != None):
        for game in games:
            if game.id == g_id:
                for pl in game.players:
                    if pl[0] == p_id:
                        if p in pl[3]:
                            return render_template("problem.html", results=pl[3][p], data=data)
                        return render_template("problem.html", results=False, data=data)
    return render_template("problem.html", results=False, data=data)

# GAME CREATION/JOINING
def random_id():
    return "".join([random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(6)])

def random_player_id():
    return "".join([random.choice(string.ascii_uppercase + string.ascii_lowercase + "1234567890") for _ in range(20)])

class Game:
    def __init__(self, problems:list, totalTime, tst:str="off", doTeams:bool=False):
        self.id = random_id()
        self.players = []
        self.status = "waiting"
        #time is in minutes
        try:
            self.time = int(totalTime) * 60
        except:
            self.time = -1
        self.teams = doTeams
        if tst == "on":
            self.tst = "true"
        else:
            self.tst = "false"
        print(self.tst)
        self.problems = [problem.rstrip() for problem in problems]
        print("created game", self.id)
        print("problems:", problems)
        save_game()
    def add_player(self, name):
        player_id = random_player_id()
        # [player id, player name, score for each problem, results for each problem, time of last successful submission]
        self.players.append([player_id, name, [0] * len(self.problems), {}, 0])
        save_game()
        return player_id
    def start(self):
        self.status = "started"
        self.start_time = time.time()
        save_game()
    def give_points(self, player, problem, points):
        if self.time_remaining() < -1:
            return
        problem_index = self.problems.index(problem)
        for pl in self.players:
            if pl[0] == player:
                if pl[2][problem_index] != 0:
                    if pl[2][problem_index] < points:
                        pl[2][problem_index] = points
                        pl[4] = time.time()
                else:
                    pl[2][problem_index] = points
                    if points > 0:
                        pl[4] = time.time()
        save_game()
    def time_remaining(self):
        if self.time == -1:
            return -1
        return self.time - (time.time() - self.start_time)
    def is_duplicate_name(self, name):
        for player in self.players:
            if name.strip() == player[1].strip():
                return True
        return False

def save_game():
    with open(GAME_FILE, "wb") as f:
        pickle.dump(games, f)

# MAIN
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            name = request.form["player_name"]
            id = request.form["game_id"]
        except:
            return render_template("index.html")
        id = id.rstrip().upper()
        for game in games:
            if game.id == id :
                if not game.is_duplicate_name(name):
                    player = game.add_player(name)
                    return redirect(f"/waiting?id={id}&player={player}")
                elif game.teams:
                    for player in game.players:
                        if player[1] == name:
                            return redirect(f"/waiting?id={id}&player={player[0]}")
    return render_template("index2.html")

# ABOUT
@app.route("/about")
def about():
    return render_template("about.html")

# JOIN
@app.route("/join", methods=["GET", "POST"])
def join():
    id = request.args.get("id")
    if request.method == "POST":
        try:
            name = request.form["player_name"]
        except:
            return render_template("join.html", id=id)
        id = id.rstrip().upper()
        for game in games:
            if game.id == id and not game.is_duplicate_name(name):
                player = game.add_player(name)
                return redirect(f"/waiting?id={id}&player={player}")
    return render_template("join.html", id=id)

def hash_password(password):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()

def is_admin(email, username, hashedPass):
    print("lol")
    if email == "jierueic@gmail.com" and username == "knosmos" and check_password("c8cd035724dd2cc48f87c17f21c4cb7f9bdf9cf767bc88e5fcefefbf8f73dd0f:533a7722507f4d1da1bdfca16bf70675", hashedPass):
        return True
    if email == "nicholas.d.hagedorn@gmail.com" and username == "Nickname" and check_password("6d6438706baee7793b76597a15628859cf9b47c0097f814d06187247d120ceb7:6316c3b35173482db353c2a2baa8301e", hashedPass):
        return True

    return False

def is_account(cred, email_or_username, password):
    return check_password( cred[2], password) and (email_or_username == cred[0] or email_or_username == cred[1])

# This class is unused; it remains in the code in case user accounts are implented in the future
class User:
    def __init__(self, email, username, password):
        self.user_ID = str(id(str(email)+str(username)+str(hash_password(password))))
        self.isAdmin = is_admin(email, username, password)
        self.credentials = [email, username, hash_password(password), self.user_ID, self.isAdmin]

    def is_repeat(self, users):
        for otherUser in users:
            if otherUser.credentials[0] == self.credentials[0] or otherUser.credentials[1] == self.credentials[1]:
                return True
        return False

    def store_account(self):
        open("users/" + self.user_ID + ".json", "w", encoding='utf-8').write(json.dumps(self.credentials))

@app.route("/log_in", methods=["GET", "POST"])
def log_in():
    if request.method == "POST":
        try:
            emailUsername = request.form["emailUsername"].strip()
            password = request.form["password"].strip()

            for filename in glob.glob(os.path.join("users/", '*.json')): #only process .JSON files in folder.
                with open(filename, encoding='utf-8') as currentFile:
                    data = json.load(currentFile)
                    if is_account(data, emailUsername, password):

                        userID = adminPass
                        isAdmin = data[4]

                        return render_template(
                            "log_in.html",
                            admin = isAdmin,
                            userid = userID
                        )
                        # return redirect(f"/?id={userID}") #change to put userID in the URL
        except:
            pass

    return render_template("log_in.html")

@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    if request.method == "POST":
        email = request.form["email"].strip()
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        user = User(email, username, password)
        if "@" in email and len(username) > 4 and len(password) > 4 and not user.is_repeat(users):
            user.store_account()
            userID = user.credentials[3]
            return redirect(f"/") #change to put userID in the URL
    return render_template("sign_up.html")

@app.route("/select", methods=["GET", "POST"])
def problem_select():
    if request.method == "POST":
        print("value is")
        print(request.form.get("tst"))
        game = Game(request.form["problems"].rstrip().split("\n"), request.form["timer"], request.form.get("tst"), request.form.get("teams"))
        games.append(game)
        return redirect(f"host_waiting?id={game.id}")
    problems = get_problem_names()
    public_problems = []
    if not admin_check(request):
        print("not admin")
        for problem in problems:
            if problem["status"] == "public":
                public_problems.append(problem)
        return render_template("select.html", problems = public_problems)

    # admins have access to all problems
    for problem in problems:
        print(problem["status"])
        if problem["status"] == "public" or problem["status"] == "publvate":
            public_problems.append(problem)
    return render_template("select.html", problems = public_problems)

@app.route("/host_waiting", methods=["GET", "POST"])
def host():
    id = request.args.get("id")
    if request.method == "POST":
        for game in games:
            if game.id == id:
                game.start()
                break
        return redirect(f"/host_scoreboard?id={id}")
    return render_template("host_waiting.html", id=id)

@app.route("/waiting", methods=["GET"])
def waiting():
    id = request.args.get("id")
    player = request.args.get("player")
    player_name = "unknown"
    for game in games:
        if game.id == id:
            for p in game.players:
                if p[0] == player:
                    player_name = p[1]
    return render_template("waiting.html", id=request.args.get("id"), player=player_name, player_id=player)

@app.route("/api/game_status", methods=["GET"])
def get_game_status():
    id = request.args.get("id")
    for game in games:
        if game.id == id:
            return '{"status":"%s"}' % game.status

@app.route("/api/players", methods=["GET"])
def get_players():
    id = request.args.get("id")
    for game in games:
        if game.id == id:
            return json.dumps(game.players)
    return "error"

# SCOREBOARD

@app.route("/scoreboard", methods=["GET"])
def scoreboard():
    id = request.args.get("id")
    player = request.args.get("player")
    for game in games:
        if game.id == id:
            for p in game.players:
                if p[0] == player:
                    return render_template(
                        "scoreboard.html",
                        id=id,
                        player = player,
                        player_name = p[1],
                        problems = game.problems,
                        tst = game.tst,
                        time = game.time_remaining()
                    )
    abort(404)

@app.route("/host_scoreboard", methods=["GET"])
def scoreboard_host():
    id = request.args.get("id")
    for game in games:
        if game.id == id:
            return render_template(
                "host_scoreboard.html",
                id = id,
                problems = game.problems,
                tst = game.tst,
                time = game.time_remaining()
            )
    abort(404)

# ERROR PAGES
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html', data = traceback.format_exc()), 500

@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html'), 401

@app.route("/crash")
def crash():
    raise Exception("Intentional crash tester function triggered")
    return

# Load games
GAME_FILE = "games/game.pkl"
if os.path.exists(GAME_FILE):
    with open(GAME_FILE, "rb") as f:
        games = pickle.load(f)

''' # Uncomment to remove old games
running_games = []
for game in games:
    if game.time_remaining() >= -1:
        running_games.append(game)
games = running_games
'''

if __name__ == "__main__":
    app.run("127.0.0.1")
