import grader
import json
import os
import random
import time
import markdown
import uuid 
import hashlib
import glob
from sys import argv
import string
from datetime import datetime
from flask import Flask, request, render_template, redirect, make_response
app = Flask(__name__)

port = int(argv[1]) if len(argv) > 1 else 5000

max_testcases = 10
games = []
users = []
adminPass = ''.join(random.choice(string.ascii_lowercase) for i in range(40))

# PROBLEM CREATION/EDITING/SOLUTION GRADING

def get_problem_names():
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
    problems.sort(key = lambda x:
        {
            "trivial": 0, "easy": 1, "medium": 2, "hard": 3, "very hard": 4
        }[x["difficulty"].lower()] if "difficulty" in x else 5)
    return problems

def admin_check(req):
    return (req.cookies.get("userid") == adminPass):

@app.route("/list", methods=["GET","POST"])
def catalogue():
    if admin_check(request):
        return render_template("list.html", problems = get_problem_names())
    return "You are not authorized to access this page."

@app.route("/public", methods=["GET","POST"])
def public_catalogue():
    return render_template("list_public.html", problems = get_problem_names())

@app.route("/upload", methods=["GET", "POST"])
def upload():
    # ensure only admin can access this page
    if not admin_check(request):
        return "You are not authorized to access this page."

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
        return "You are not authorized to access this page."
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

def get_old_results(p: str):
    cookie = request.cookies.get(f"results_{p}")
    if cookie is None:
        return False
    cookie = json.loads(cookie)

@app.route('/problem', methods=["GET", "POST"])
def problem():
    p = request.args.get("id")
    with open("problems/" + p + ".json", encoding='utf-8') as f:
        data = json.load(f)
        data["description"] = markdown.markdown(data["description"])
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
        for res in results["tests"]:
            if res[0] == "AC":
                num_ac += 1
        
        g_id = request.args.get("g_id")
        p_id = request.args.get("player")
        if (g_id != None) and (p_id != None):
            print("giving score to", p_id, "from game", g_id)
            for game in games:
                if game.id == g_id:
                    for pl in game.players:
                        if pl[0] == p_id:
                            if num_ac == len(results["tests"]):
                                num_points = 100
                            elif num_ac > 1:
                                num_points = 80 * (num_ac - 1)/(len(results["tests"]) - 1)
                            else:
                                num_points = -0.1
                            game.give_points(p_id, p, num_points)
                            pl[3][p] = results
        response = make_response(render_template("problem.html", results=results, data=data))
        response.set_cookie(f"results_{p}", json.dumps(results), max_age=60*60*24)
        return response
    else:
        g_id = request.args.get("g_id")
        p_id = request.args.get("player")
        if (g_id != None) and (p_id != None):
            for game in games:
                if game.id == g_id:
                    for pl in game.players:
                        if pl[0] == p_id:
                            if p in pl[3]:
                                return render_template("problem.html", results=pl[3][p], data=data)
                            return render_template("problem.html", results=get_old_results(p), data=data)

        return render_template("problem.html", results=get_old_results(p), data=data)

# GAME CREATION/JOINING
def random_id():
    return "".join([random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(6)])

class Game:
    def __init__(self, problems, totalTime, freezeTime, doTeams):
        self.id = random_id()
        self.players = []
        self.status = "waiting"
        #time is in minutes
        try:
            self.time = int(totalTime) * 60
        except:
            self.time = -1
        try:
            self.freeze = int(freezeTime) * 60
        except:
            self.freeze = 0
        self.teams = doTeams
        self.problems = [problem.rstrip() for problem in problems]
        print("created game", self.id)
        print("problems:", problems)
    def add_player(self, name):
        player_id = random_id()
        # [player id, player name, score for each problem, results for each problem, time of last successful submission]
        self.players.append([player_id, name, [0] * len(self.problems), {}, 0])
        return player_id
    def start(self):
        self.status = "started"
        self.start_time = time.time()
    def give_points(self, player, problem, points):
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
    def time_remaining(self):
        if self.time == -1:
            return -1
        return self.time - (time.time() - self.start_time)
    def is_duplicate_name(self, name):
        print(name)
        print(self.players)
        print("triggered")
        for player in self.players:
            print(player)
            print(player[1])
            if name.strip() == player[1].strip():
                print("true")
                return True
        print("false")
        return False

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
            if game.id == id and not game.is_duplicate_name(name):
                player = game.add_player(name)
                return redirect(f"/waiting?id={id}&player={player}")
    return render_template("index2.html")

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
    actual_pass = hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()
    return password == actual_pass

def is_admin(email, username, hashedPass):
    if email == "jierueic@gmail.com" and username == "knosmos" and check_password("c8cd035724dd2cc48f87c17f21c4cb7f9bdf9cf767bc88e5fcefefbf8f73dd0f:533a7722507f4d1da1bdfca16bf70675", hashedPass):
        return True
    if email == "nicholas.d.hagedorn@gmail.com" and username == "Nickname" and check_password("6d6438706baee7793b76597a15628859cf9b47c0097f814d06187247d120ceb7:6316c3b35173482db353c2a2baa8301e", hashedPass):
        return True
    
    return False

def is_account(cred, email_or_username, password):
    return check_password( cred[2], password) and (email_or_username == cred[0] or email_or_username == cred[1])
    
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
        game = Game(request.form["problems"].rstrip().split("\n"), request.form["timer"], request.form["freezer"], request.form.get("teams"))
        games.append(game)
        return redirect(f"host_waiting?id={game.id}")
    problems = get_problem_names()
    public_problems = []
    for problem in problems:
        if problem["status"] == "public":
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
                        freezeTime = game.freeze,
                        time = game.time_remaining()
                    )

@app.route("/host_scoreboard", methods=["GET"])
def scoreboard_host():
    id = request.args.get("id")
    for game in games:
        if game.id == id:
            return render_template(
                "host_scoreboard.html",
                id = id,
                problems = game.problems,
                freezeTime = game.freeze,
                time = game.time_remaining()
            )
    return "error"

if __name__ == "__main__":
    app.run("0.0.0.0", port)
