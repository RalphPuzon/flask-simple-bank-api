# I M P O R T S------------------------------------------------------
from flask import Flask, jsonify, request
from flask_restful import Api, Resource
from pymongo import MongoClient
import bcrypt

# I N I T I A L I Z A T I O N S -------------------------------------
app = Flask(__name__)
api = Api(app)
client = MongoClient("mongodb://db:27017")
db = client.BankApiDB
users = db["Users"]

# H E L P E R _ F U N C T I O N S -----------------------------------
# general json response function:
def json_response(message, status_code):
	returnJSON = {
		"Message": message,
		"Status Code": status_code
	}

	return returnJSON

# checking if username exists
def check_user_in_db(username):
	if users.find({"Username": username}).count==0:
		return False
	else:
		return True

# check password:
def authenticate_user(username, password):

	if check_user_in_db(username) == False:
		returnJSON = json_response("User not in database", 300)
		return returnJSON, False

	stored_hash = users.find({"Username":username})[0]["Password"] 

	if bcrypt.hashpw(password, stored_hash) != stored_hash:
		returnJSON = json_response("Username and/or password is incorrect", 300)
		return returnJSON, False

	return json_response("ok", 200), True

# return balance and debt of user:
def user_balance(username):
	return users.find({"Username": username})[0]["Balance"]

def user_debt(username):
	return users.find({"Username": username})[0]["Debt"]

#update balance and debt of user:
def update_balance(username, new_balance):
	users.update({"Username":username},
			         {"$set": {"Balance":new_balance}})

def update_debt(username, new_debt):
	users.update({"Username":username},
			         {"$set": {"Debt":new_debt}})

# C L A S S _ R E S O U R C E S -------------------------------------
# register user:
class Register(Resource):
	def post(self):

		#	fetch
		postedData = request.get_json()

		#	verify
		username = postedData["username"]
		password = postedData["password"].encode('utf-8')
		# this is separated as a function in the tutorial.
		if users.find({"Username": username}).count() > 0:
			returnJSON = {
				"Message": "Username already taken, please enter a new one.",
				"Status Code": 300
			}

			return jsonify(returnJSON)

		#	insert into db

		hashed_pw = bcrypt.hashpw(password, bcrypt.gensalt())

		users.insert_one({"Username": username,
						  "Password": hashed_pw,
						  "Balance": 0,
						  "Debt": 0
						  })

		#	return ok status
		returnJSON = {
			"Message": "Successfully registered user " + str(username),
			"Status Code": 200
		}

		return jsonify(returnJSON)

# add balance to acct:
class Add(Resource):
	def post(self):
		# fetch
		postedData = request.get_json()

		username = postedData['username']
		password=postedData['password'].encode('utf-8')
		amount_to_add = postedData['amount']

		# authenticate the user
		error, state = authenticate_user(username, password)
		if state == False:
			return jsonify(error)

		# amount
		if amount_to_add <= 0:
			return jsonify(json_response("amount must be greater than 0", 300))

		current_balance = user_balance(username)
		# adding bank fees, let's say $1/transaction:
		amount_to_add -= 1 #take a dollar from to add
		bank_cash = user_balance("BANK")
		update_balance("BANK", bank_cash + 1) #give dollar to bank

		#add the remaining money to user's account:
		update_balance(username, current_balance + amount_to_add)
		message = "An amount of " + str(amount_to_add) + \
		          " was successfully added into " + \
				  username + "'s account"
		return jsonify(json_response(message, 200))

# balance transfer resource:
class Transfer(Resource):
	def post(self):
		# fetch
		postedData = request.get_json()

		username = postedData['username']
		password = postedData['password'].encode('utf-8')
		user_to_send_to = postedData['to'] 
		amount_to_send = postedData['amount']

		if username == user_to_send_to:
			message = "You transfer money to yourself"
			return jsonify(json_response(message, 300))

		# authenticate the user
		error, state = authenticate_user(username, password)
		if state == False:
			return jsonify(error)

		# check that user has sufficient funds:
		curr_user_balance = user_balance(username)
		if curr_user_balance < amount_to_send:
			message = "Insufficient funds in your account, please add or take a loan"
			return jsonify(json_response(message, 300))

		# check that the other user exists:
		if check_user_in_db(user_to_send_to) == False:
			returnJSON = json_response("Receiving user not in database", 300)
			return jsonify(returnJSON)

		#get balances of both users and the bank:
		sender_bal = user_balance(username)
		recvr_bal = user_balance(user_to_send_to)
		bank_bal = user_balance("BANK")

		# process the one dollar transaction fee:
		update_balance("BANK", bank_bal + 1)
		# send the money minus the transaction fee:
		update_balance(user_to_send_to, recvr_bal + amount_to_send-1)
		# reflect the subrtraction on the sender's balance:
		update_balance(username, sender_bal - amount_to_send)

		#success message
		message = "An amount of " + str(amount_to_send) + \
		          " was successfully sent to " + \
				  user_to_send_to + "'s account"
		return jsonify(json_response(message, 200))

# check balance api resource:
class Balance(Resource):
	def post(self):
		# fetch
		postedData = request.get_json()

		username = postedData['username']
		password = postedData['password'].encode('utf-8')

		# authenticate the user
		error, state = authenticate_user(username, password)
		if state == False:
			return jsonify(error)

		# return user doc while hiding password and id using projection
		returnJSON = users.find({"Username": username},
			                    {"Password":0, "_id": 0})[0]

		#return
		return jsonify(returnJSON)

# user takes loan
class Takeloan(Resource):
	def post(self):
		# fetch
		postedData = request.get_json()

		username = postedData['username']
		password = postedData['password'].encode('utf-8')
		loan_amount = postedData['amount']

		# authenticate the user
		error, state = authenticate_user(username, password)
		if state == False:
			return jsonify(error)

		curr_user_balance = user_balance(username)
		curr_user_debt = user_debt(username)
		update_balance(username, curr_user_balance + loan_amount)
		update_debt(username, curr_user_debt + loan_amount)
		message = username + " took a loan of " + str(loan_amount) + "."

		return jsonify(json_response(message, 200)) 

# user pays loan
class Payloan(Resource):
	def post(self):
		# fetch
		postedData = request.get_json()

		username = postedData['username']
		password = postedData['password'].encode('utf-8')
		payment_amount = postedData['amount']

		# authenticate the user
		error, state = authenticate_user(username, password)
		if state == False:
			return jsonify(error)

		curr_user_balance = user_balance(username)
		if curr_user_balance < payment_amount:
			message = "Insufficient funds for specified payment amount"
			return jsonify(json_response(message, 300))

		curr_user_debt = user_debt(username)
		update_balance(username, curr_user_balance - payment_amount)
		update_debt(username, curr_user_debt - payment_amount)

		message = username + " paid " + str(payment_amount) + " towards their debt."
		return jsonify(json_response(message, 200)) 

# A D D _ R E S O U R C E S -----------------------------------------
api.add_resource(Register, "/register")
api.add_resource(Add, "/add")
api.add_resource(Transfer, "/transfer")
api.add_resource(Balance, "/balance")
api.add_resource(Takeloan, "/takeloan")
api.add_resource(Payloan, "/payloan")

# R U N _ M A I N ---------------------------------------------------
if __name__ == "__main__":
	app.run(host='0.0.0.0')