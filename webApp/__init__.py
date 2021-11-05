from flask import Flask, render_template, request, flash, redirect, session
import os, signal, time, pickle
from datetime import datetime
from multiprocessing import Process

import yuzdelik, forms
import spot, last_trades, reports_day, cancel_buy_orders, open_orders
import futures, last_trades_f, reports_day_f, cancel_buy_orders_f, open_orders_f
from test_routes import testnet

app = Flask(__name__)
app.register_blueprint(testnet)
app.secret_key = "super secret key"
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

users = {}

def read_users():
    global users
    with open('/var/www/webApp/users_data.pckl', 'rb') as users_data:  
        users = pickle.load(users_data)

def write_users():
    global users
    with open('/var/www/webApp/users_data.pckl', 'wb') as users_data:
        pickle.dump(users, users_data)


def is_alive(user, accout_type):
    if accout_type == "spot":
        try:
            users[user]["pid"]
        except:
            return False
    if accout_type == "futures":
        try:
            users[user]["f_pid"]
        except:
            return False
    return True

def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error)

@app.after_request
def add_header(response):
    response.cache_control.max_age = 0
    return response

@app.route("/", methods=["POST","GET"])
def index():
    global users
    read_users()

    LoginForm = forms.LoginForm()
    RegisterForm = forms.RegisterForm()

    if LoginForm.validate_on_submit():
        session["username"] = LoginForm.username.data
        return redirect("/kullanici")
    else:
        flash_errors(LoginForm)

    if RegisterForm.validate_on_submit():
        session["username"] = RegisterForm.username.data
        users[RegisterForm.username.data] = {"password": RegisterForm.password.data,"api": RegisterForm.api.data, "secret": RegisterForm.secret.data}
        print(users[RegisterForm.username.data])
        write_users()
        return redirect("/kullanici")

    return render_template("index.html", login = LoginForm, register = RegisterForm)


@app.route("/kullanici", methods=["POST", "GET"])
def kullanici():
    global users
    read_users()

    curr_user = session["username"]

    bot_control = request.args.get("bot", default = is_alive(curr_user, "spot"), type = lambda x: x == "True")     
    
    c_bot = users[curr_user]
    
    day = None
    trades = None
    commission = 0 if not c_bot.get("commission") else "%.2f" % c_bot.get("commission")

    if bot_control: 
        day = reports_day.reports(c_bot["symbol"], c_bot["api"], c_bot["secret"], False, c_bot["unit"], c_bot["step"], c_bot["time"])
        trades = last_trades.trades(c_bot["symbol"], c_bot["api"], c_bot["secret"], False)
    
    try:
        sym = c_bot["ex_sell_orders"]
        buy_stats = open_orders.open_orders(c_bot["symbol"], c_bot["api"], c_bot["secret"], False, c_bot["step"], c_bot["ex_sell_orders"], c_bot['bulk_buy_orders'])
        profit_per_sell = c_bot["unit"] * c_bot["step"] 
        all_time = ( c_bot["sell_count"], "%.2f" % (profit_per_sell*c_bot["sell_count"]) )
    except:
        buy_stats = (0,0)
        all_time = (0,0)
        
    return render_template("kullanici.html", user=curr_user, bot_control=bot_control, 
    day=day, all_time=all_time, trades=trades, buy_stats = buy_stats, commission = commission)
    
@app.route("/futures", methods=["POST", "GET"])
def futures():
    global users
    read_users()

    curr_user = session["username"]

    bot_control = request.args.get("bot", default = is_alive(curr_user, "futures"), type = lambda x: x == "True")     
    
    c_bot = users[curr_user]
    
    day = None
    trades = None
    commission = 0 if not c_bot.get("f_commission") else "%.2f" % c_bot.get("f_commission")

    if bot_control: 
        day = reports_day_f.reports(c_bot["f_symbol"], c_bot["api"], c_bot["secret"], False, c_bot["f_unit"], c_bot["f_step"], c_bot["f_time"])
        trades = last_trades_f.trades(c_bot["f_symbol"], c_bot["api"], c_bot["secret"], False)
    
    try:
        sym = c_bot["f_ex_sell_orders"]
        buy_stats = open_orders_f.open_orders(c_bot["f_symbol"], c_bot["api"], c_bot["secret"], False, c_bot["f_step"], c_bot["f_ex_sell_orders"], c_bot['f_bulk_buy_orders'])
        profit_per_sell = c_bot["f_unit"] * c_bot["f_step"] 
        all_time = ( c_bot["f_sell_count"], "%.2f" % (profit_per_sell*c_bot["f_sell_count"]) )
    except:
        buy_stats = (0,0)
        all_time = (0,0)
        
    return render_template("futures.html", user=curr_user, bot_control=bot_control, 
    day=day, all_time=all_time, trades=trades, buy_stats = buy_stats, commission = commission)

@app.route("/f_bot", methods=["POST"])
def f_bot():
    global users
    read_users()
    user = request.args.get("user")
    
    if request.form.get("stop"):
        for i in range(100):
            time.sleep(0.01)
            try:
                os.system(f"kill -9 {users[user]['f_pid']}")
            except Exception as e:
                print(e)
                pass
        
        cancel_buy_orders_f.cancel(users[user]['api'], users[user]['secret'], False, users[user]['f_symbol'])
        users[user].pop("f_pid", None)
        write_users()
        return redirect(f"/futures?user={user}&bot=False")

    api = users[user]["api"]    
    secret = users[user]["secret"]

    symbol = request.form.get("f_coin")
    step = request.form.get("f_step")
    unit = request.form.get("f_unit")
    grids = request.form.get("f_grids")
    leverage = request.form.get("f_leverage")

    if len(request.form) >= 4:  # formdan gelen veriler symbol, step, yuzde vb leri içerirse 4ten büyük olur
        
        bot = Process(target=futures.bot, args=(symbol, step, unit, grids, leverage, api, secret, False, user))
        time.sleep(0.3)
        bot.start()
        now = datetime.now()
        time.sleep(0.3)

        users[user].update({"f_symbol": symbol, "f_step": float(step), "f_unit": float(unit),
                    "f_grids": int(grids), "f_pid":bot.pid, "f_sell_count": 0, "f_time":now, "f_commission": 0.0})
        write_users()

    return redirect(f"/futures?user={user}&bot=True")


@app.route("/bot", methods=["POST"])
def bot():
    global users
    read_users()
    user = request.args.get("user")
    
    if request.form.get("stop"):
        for i in range(100):
            time.sleep(0.01)
            try:
                os.system(f"kill -9 {users[user]['pid']}")
            except Exception as e:
                print(e)
                pass
        
        cancel_buy_orders.cancel(users[user]['api'], users[user]['secret'], False, users[user]['symbol'])
        users[user].pop("pid", None)
        write_users()
        return redirect(f"/kullanici?user={user}&bot=False")

    api = users[user]["api"]
    secret = users[user]["secret"]

    symbol = request.form.get("coin")
    step = request.form.get("step")
    yuzde = request.form.get("yuzde")
    unit = request.form.get("unit")
    grids = request.form.get("grids")

    if len(request.form) >= 4:  # formdan gelen veriler symbol, step, yuzde vb leri içerirse 4ten büyük olur
        
        bot = Process(target=spot.bot, args=(symbol, step, unit, grids, api, secret, False, user))
        time.sleep(0.3)
        bot.start()
        now = datetime.now()
        time.sleep(0.3)

        users[user].update({"symbol": symbol, "step": float(step), "unit": float(unit),
                    "grids": int(grids), "pid":bot.pid, "sell_count": 0, "time":now, "commission": 0.0})
        write_users()

    return redirect(f"/kullanici?user={user}&bot=True")
