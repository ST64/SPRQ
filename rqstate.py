from backend.playerstate import PlayerState
from backend.jsonhandler import JSONHandler
from backend.rqmap import RQMap
import backend.rqflags as flags
import time
import random
import math
import itertools
DEBUG = 1
modeTable = {
	"1.0" : flags.RQMode.M_10,
	"1.1" : flags.RQMode.M_11,
	"SP" : flags.RQMode.M_15,
	"COOP" : flags.RQMode.M_COOP,
	"RAND" : flags.RQMode.M_RAND
}
class RQState:
	def __init__(self, filename):
		self.savedData = JSONHandler(filename)
		self.mapHandler = RQMap(self.savedData)
		self.mode = flags.RQMode.M_15
		self.players = {}

	def loadstate(self, filename=None):
		self.savedData.loadState(filename)

	def savestate(self, filename=None):
		for player in self.players:
			self.savePlayer(player)
		self.savedData.saveState(filename)

	def levelUp(self, playerid, stat):
		if self.players[playerid].levelUp(stat):
			self.players[playerid].printStats()

	def loadPlayer(self, playerid):
		self.players[playerid] = self.savedData.loadPlayer(playerid)

	def savePlayer(self, playerid):
		self.savedData.savePlayer(playerid, self.players[playerid])

	def getMessages(self, playerid):
		return self.players[playerid].getMessages()

	def fastTravel(self, playerid, message):
		self.mapHandler.fastTravel(self.players[playerid], message)

	def checkWin(self, playerid, usedItem):
		if self.players[playerid].state == "battle" and self.players[playerid].battle["hp"] <= 0:
			if usedItem not in ["attack", "heal", "block"]:
				self.players[playerid].writeMessage( self.players[playerid].battle["text"]["iwin"].format(usedItem))
			else:
				self.players[playerid].writeMessage( self.players[playerid].battle["text"]["win"].format(usedItem))
			self.players[playerid].money += self.players[playerid].battle["money"]
			for item in self.players[playerid].battle["drops"]:
				if random.randrange(256) <= self.players[playerid].battle["drops"][item]:
					self.players[playerid].addItem(item)
			self.players[playerid].addXP(self.players[playerid].battle["xp"], self.players[playerid].battle["level"])
			self.mapHandler.setState(self.players[playerid], "map")
			return True
		else:
			return False

	def checkLose(self, playerid, usedItem):
		if self.players[playerid].hp <= 0:
			if self.players[playerid].battle["turn"] == 0:
				self.players[playerid].writeMessage( self.players[playerid].battle["text"]["plose"])
			elif usedItem:
				self.players[playerid].writeMessage( self.players[playerid].battle["text"]["ilose"].format(usedItem))
			else:
				self.players[playerid].writeMessage( self.players[playerid].battle["text"]["lose"].format(usedItem))
			self.killPlayer(playerid)
			return True
		else:
			return False

	def doMove(self, playerid, message):
		if message in self.savedData["costs"]:
			cost = self.savedData["costs"][message]
			if self.players[playerid].sp >= cost:
				self.players[playerid].sp -= cost
				return True
			else:
				self.players[playerid].writeMessage( f"You don't have enough sp to {message}")
		return False

	def handleBattle(self, playerid, message, usedItem):
		messagelist = message.split()
		defMul = self.players[playerid].defMul
		if self.doMove(playerid, messagelist[0]):
			if messagelist[0] == "attack":
				self.players[playerid].damageNPC(self.players[playerid].atk)
			elif messagelist[0] == "heal":
				self.players[playerid].hp = self.players[playerid].maxHP
			elif messagelist[0] == "block":
				defMul = self.players[playerid].defMul/2

		if self.checkWin(playerid, usedItem):
			return

		damage = self.players[playerid].battle["atk"]
		message = self.players[playerid].battle["text"]["turn"]
		if self.players[playerid].battle["type"] == "bosses":
			attacks = self.players[playerid].battle["attacks"]
			rChoices = []
			if "charge" in self.players[playerid].battle:  # Boss is charged
				rChoices = ["charge", "catk"]
			else:  # Boss is not charged
				rChoices = [x for x in attacks.keys() if x != "catk" and self.players[playerid].battle["hp"] <= attacks[x]["maxhp"]]
			rWeights = [*itertools.accumulate([attacks[x]["probability"] for x in rChoices]), 256]
			rChoices.append(None)
			chosen = random.choices(rChoices, cum_weights=rWeights)[0]
			if chosen == "charge":
				self.players[playerid].battle["charge"] = self.players[playerid].battle.get("charge", 0) + attacks[chosen]["atk"]
				damage = 0
				message = attacks[chosen]["text"].format(self.players[playerid].battle["charge"])
			elif chosen == "catk":
				damage = self.players[playerid].battle["charge"] + attacks[chosen]["atk"]
				message = attacks[chosen]["text"]
			elif chosen:
				damage = attacks[chosen]["atk"]
				message = attacks[chosen]["text"]

		self.players[playerid].hp -= round(defMul * damage * (time.monotonic() - self.players[playerid].battle["time"]))
		if not self.checkLose(playerid, usedItem):
			self.players[playerid].writeMessage( message)
			self.players[playerid].battle["time"] = time.monotonic()
			self.players[playerid].battle["turn"] += 1

	def killPlayer(self, playerid):
		room = self.mapHandler.getRoom(self.players[playerid])
		room["items"] += self.players[playerid].reset()
		respawnData = self.savedData["regions"][room["region"]]
		self.players[playerid].location = respawnData["room"]
		self.players[playerid].writeMessage(respawnData["message"])

	def printState(self, playerid):
		player = self.players[playerid]
		if player.state == "map":
			room = self.savedData["rooms"][self.players[playerid].location]
			rmessage = [room["name"], room["info"], "Items:"] + room["items"]
			if self.players[playerid].hasFlag(flags.RQFlags.F_NEW_ITEMS):
				if "flashlight" in self.players[playerid].powerups:
					rmessage.append("Exits: ")
					rmessage += [x for x in room["exits"] if x != "none"]
			rmessage.append("Region: " + room["region"])
			self.players[playerid].writeMessage( "\n".join(rmessage))
		elif player.state == "battle":
			self.players[playerid].writeMessage( f"HP: {player.hp}")
			self.players[playerid].writeMessage( f"SP: {player.sp}")
			self.players[playerid].writeMessage( f"NPC Name: {self.players[playerid].battle['name']}")
			self.players[playerid].writeMessage( f"NPC HP: {self.players[playerid].battle['hp']}")

	def handleShop(self, playerid, command, items):
		room = self.savedData["rooms"][self.players[playerid].location]
		if room["name"] in self.savedData["shops"]:
			shopdata = self.savedData["shops"][room["name"]]
			nonexistentItems = []
			if command == "buy":
				for item in items:
					if item not in shopdata:
						self.players[playerid].writeMessage( f"Item {item} is not in this shop")
					elif self.savedData["items"][item]["cost"] > self.players[playerid].money:
						self.players[playerid].writeMessage( f"You can't afford {item}!!")
					else:
						self.players[playerid].money -= self.savedData["items"][item]["cost"]
						if not self.players[playerid].addItem( item):
							break
			else:
				for item in items:
					if not self.players[playerid].removeItem( item):
						nonexistentItems.append(item)
					else:
						self.players[playerid].money += self.savedData["items"][item]["cost"]//2
				if nonexistentItems:
					self.players[playerid].writeMessage( f"Error: Items {', '.join(nonexistentItems)} not found")
		else:
			self.players[playerid].writeMessage( f"{room} is not a shop")

	def handleItems(self, playerid, command, items):
		room = self.savedData["rooms"][self.players[playerid].location]
		nonexistentItems = []
		if command == "get":
			for item in items:
				if item in room["items"]:
					if not self.players[playerid].addItem(item):
						break
					room["items"].remove(item)
				else:
					nonexistentItems.append(item)
		else:
			for item in items:
				if not self.players[playerid].removeItem(item):
					nonexistentItems.append(item)
				elif command == "drop":
					room["items"].append(item)
		if nonexistentItems:
			self.players[playerid].writeMessage( f"Error: Items {', '.join(nonexistentItems)} not found")

	def attackItem(self, playerid, item):
		damage = self.savedData["items"][item]["atk"]
		weakness = "soup"
		if "weakness" in self.players[playerid].battle:
			weakness = self.players[playerid].battle["weakness"]
		if weakness == item:
			damage = damage * 2
		self.players[playerid].damageNPC(damage)

	def useItems(self, playerid, message):
		items = message.split(", ")
		nonexistentItems = []
		lastItem = ""
		aliasList = {
			"s" : "soup",
			"ss" : "souper soup",
			"bs" : "battle soup",
			"hs" : "healthy soup",
			"sl" : "salad"
		}
		for item in items:
			item = aliasList.get(item, item)
			if item in self.players[playerid].items:
				itemdata = self.savedData["items"][item]
				if itemdata["type"] == "any":
					self.players[playerid].hp = min(self.players[playerid].maxHP, self.players[playerid].hp + itemdata["hp"])
					self.players[playerid].sp = min(self.players[playerid].maxSP, self.players[playerid].sp + itemdata["sp"])
					if self.players[playerid].state == "battle":
						self.attackItem(playerid, item)
						lastItem = item
				elif itemdata["type"] == "special":
					if self.players[playerid].state == "battle":
						self.attackItem(playerid, item)
						lastItem = item
					else:
						self.players[playerid].powerups.add(item)
				elif itemdata["type"] == "battle" and self.players[playerid].state == "battle":
					self.attackItem(playerid, item)
					lastItem = item
				elif itemdata["type"] == "powerup":
					if item in ["bag", "suitcase"]:
						self.players[playerid].itemCapacity = itemdata["data"]
					self.players[playerid].powerups.add(item)
				else:
					self.players[playerid].writeMessage( f"Error: invalid item {item}")
				self.players[playerid].removeItem(item)
			else:
				nonexistentItems.append(item)
		if nonexistentItems:
			self.players[playerid].writeMessage( f"Error: Items {', '.join(nonexistentItems)} not found")
		if self.players[playerid].state == "battle":
			self.handleBattle(playerid, message, item)

	def openDispenser(self, playerid, message):
		if message not in self.savedData["dispensers"]["rooms"].keys():
			self.players[playerid].writeMessage( f"You can't open {message}!")
		elif self.players[playerid].location not in self.savedData["dispensers"]["rooms"][message]:
			self.players[playerid].writeMessage( f"You can't {message} here!")
		else:
			dispenserDict = self.savedData["dispensers"][message]
			item = random.choices([*dispenserDict.keys()], weights=dispenserDict.values())[0]
			self.players[playerid].addItem(item)

	def parseMessage(self, playerid, message):
		messagelist = message.split()
		if DEBUG == 1:
			if messagelist[0] == "modmove":
				self.players[playerid].location = message[8:]
				return
			elif messagelist[0] == "modmoney":
				self.players[playerid].money += int(messagelist[1])
				return
			elif messagelist[0] == "modgive":
				self.players[playerid].addItem(messagelist[1])
				return
			elif messagelist[0] == "modxp":
				self.players[playerid].addXP(int(messagelist[1]), 1)
				return
			elif messagelist[0] == "modlevel":
				self.players[playerid].level = int(messagelist[1])
				return

		if messagelist[0] == "setmode":
			messagelist[1] = messagelist[1].upper()
			if messagelist[1] in modeTable:
				self.killPlayer(playerid)
				self.savedData.savePlayer(playerid, PlayerState())
				self.players[playerid] = self.savedData.loadPlayer(playerid)
				self.players[playerid].mode = modeTable[messagelist[1]]
				if self.players[playerid].mode == flags.RQMode.M_RAND:
					self.players[playerid]._items = [*self.savedData["items"].keys()]
				self.players[playerid].writeMessage(f"Your mode is now set to {messagelist[1]}")
			else:
				self.players[playerid].writeMessage(f"{messagelist[1]} is not a mode! Valid modes are: {[*modeTable.keys()]}")
		elif messagelist[0] == "use":
			self.useItems(playerid, " ".join(messagelist[1:]))
		elif self.players[playerid].state == "map":
			if messagelist[0][:4] == "inv":
				self.players[playerid].printInventory()
			elif messagelist[0] == "profile":
				self.players[playerid].printStats()
				self.players[playerid].printInventory()
			elif messagelist[0] == "ride":
				self.fastTravel(playerid, message[5:])
			elif messagelist[0] == "panic":
				self.killPlayer(playerid)
			elif messagelist[0] in ["buy", "sell"]:
				command = messagelist[0]
				items = " ".join(messagelist[1:]).split(", ")
				self.handleShop(playerid, command, items)
			elif messagelist[0] in ["get", "drop", "destroy"]:
				command = messagelist[0]
				items = " ".join(messagelist[1:]).split(", ")
				self.handleItems(playerid, command, items)
			elif messagelist[0] == "levelup":
				self.levelUp(playerid, messagelist[1])
			elif messagelist[0] == "open":
				self.openDispenser(playerid, messagelist[1])
			elif self.mapHandler.movePlayer(self.players[playerid], message):
				self.mapHandler.handleRoom(self.players[playerid])
		elif self.players[playerid].state == "battle":
			if messagelist[0][:4] == "inv":
				self.printState(playerid)
				self.players[playerid].printInventory()
			elif messagelist[0] in ["attack", "heal", "block"]:
				self.handleBattle(playerid, message, messagelist[0])
			elif random.randrange(256) > 100:
				self.players[playerid].writeMessage( self.players[playerid].battle["text"]["norun"])
				self.killPlayer(playerid)
			elif self.mapHandler.movePlayer(self.players[playerid], message):
				self.players[playerid].writeMessage( self.players[playerid].battle["text"]["run"])
				self.mapHandler.setState(self.players[playerid], "map")
			else:
				self.handleBattle(playerid, message, False)
