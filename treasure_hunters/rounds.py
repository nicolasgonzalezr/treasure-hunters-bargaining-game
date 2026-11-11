# -*- coding: utf-8 -*-
"""
Created on Thu Jul 31 07:17:46 2025

@author: Usuario
"""
import random
import math

def generate_round_settings(sessionPlayers):
	roundSettings = {}
	roundCounter = 1

	# Practice match, match indices start at 1
	roundSettings[1] = {
		'matchType': 'practice',
		'rounds': [roundCounter, roundCounter + 1],
	}
	roundCounter += 2

	# Avatar match
	roundSettings[2] = {
		'matchType': 'avatar',
		'rounds': [roundCounter, roundCounter + 1],
	}
	roundCounter += 2

	# Determine number of face-to-face matches
	if sessionPlayers >= 3:
		totalMatches = 3 # Cap to 3 matches
	elif sessionPlayers == 2:
		totalMatches = 1
	else: # Do not schedule F2F matches for single player session
		totalMatches = 0

	for match_index in range(3, 3 + totalMatches):
		roundSettings[match_index] = {
			'matchType': 'faceToFace',
			'rounds': [roundCounter, roundCounter + 1],
		}
		roundCounter += 2

	return roundSettings


# MAP THE ROUND NUMBER BACK TO MATCH FOR CONDITIONAL LOGIC

def get_match(roundNumber, roundSettings):
	for matchKey, matchValue in roundSettings.items():
		if roundNumber in matchValue['rounds']:
			return matchKey, matchValue['matchType']
		

# GENERATE PAIRS WITH ROUND ROBIN

def generate_matches(sessionPlayers):
	labels = [f'P{i+1}' for i in range(sessionPlayers)] # Add one so it aligns with player labels
	n = sessionPlayers
	is_odd = n % 2 != 0

	if is_odd:
		n += 1 # Add room for a bye player to even the group
		labels.append("bye") # Append bye in the last position

	# Initial permutation to force Round 1 = (0,1), (2,3), (4,5)
	# This aligns participant with terminal labels, such that no one has to move for the initial face to face round
	# Build indices, then take evens in order + odds in reverse
	perm = list(range(0, n, 2)) + list(range(n - 1, 0, -2))
	players = [labels[i] for i in perm]

	fixed = players[0]
	rotating = players[1:]
	matchesBye = {}

	for r in range(min(3, n - 1)): # If more than 3 matches are possible, cap at 3
		current = [fixed] + rotating
		pairs = []

		for i in range(n // 2):
			p1 = current[i]
			p2 = current[n - 1 - i]
			pairs.append((p1, p2))

		matchesBye[r + 1] = pairs # Match indices start at 1
		rotating = [rotating[-1]] + rotating[:-1]  # right/clockwise rotation

	# FILTER OUT BYE PLAYER FOR ROOM/TERMINAL ASSIGNMENT
	matches = {}

	for matchKey, matchPairs in matchesBye.items():
		matches[matchKey] = []
		for p1, p2 in matchPairs:
			if p1 == "bye":
				matches[matchKey].append((p2,))
			elif p2 == "bye":
				matches[matchKey].append((p1,))
			else:
				matches[matchKey].append((p1, p2))

	return matches, matchesBye


# ASSIGN PAIRS TO ROOMS

"""
Assigns match pairs to rooms for each match, ensuring players avoid the same room in consecutive matches.
Falls back to random assignment if a conflict-free allocation isn't possible.

"""

terminalRooms = {
	'T1': 1,
	'T2': 1,
	'T3': 2,
	'T4': 2,
	'T5': 3,
	'T6': 3,
}

def assign_rooms(matches, maxRooms=3):
		
	roomLabels = [f'room_{i+1}' for i in range(maxRooms)]
			
	roomLabels = roomLabels[:len(matches[1])] # FILTER OUT UNUSED ROOMS
			
	roomTerminals = {
		'room_1': ('T1', 'T2'),
		'room_2': ('T3', 'T4'),
		'room_3': ('T5', 'T6'),
	}
			
	roomAssignments = {}
			
	terminalAssignments = {}
			
	roomAssignments[1] = dict(zip(roomLabels, matches[1]))  # POPULATE FIRST MATCH ROOMS DIRECTLY, START AT 1
			
	terminalAssignments[1] = {}
			
	for room, players in roomAssignments[1].items(): # POPULATE FIRST MATCH TERMINALS DIRECTLY
		t1, t2 = roomTerminals[room]
		if len(players) == 1: # IF THE MATCH IS A BYE
			p1 = players[0]
			terminalAssignments[1][p1] = t1 # GOES TO T5 OR T3
		else:
			p1, p2 = players
			terminalAssignments[1][p1] = t1
			terminalAssignments[1][p2] = t2

	# KEEP PARTICIPANTS IN THE SAME TERMINAL FOR THE AVATAR MATCH
	roomAssignments[2], terminalAssignments[2] = roomAssignments[1].copy(), terminalAssignments[1].copy()
	# AND THE FIRST FACE TO FACE MATCH
	roomAssignments[3], terminalAssignments[3] = roomAssignments[1].copy(), terminalAssignments[1].copy()

	# SHUFFLE ROOMS FOR SUBSEQUENT MATCHES
	for matchKey, matchPairs in matches.items():

		if matchKey == 1: # SKIP FIRST FACE TO FACE MATCH, ALREADY ASSIGNED TO DEFAULT STARTING POSITIONS
			continue

		matchKey += 2 # OFFSET BY NON PAIRED MATCHES (PRACTICE + AVATAR)
			
		shuffledPairs = []

		availablePairs = []

		byePair = None
		
		# REMOVE THE BYE PLAYER FROM AVAILABLE PAIRS FOR ROOM ALLOCATION, GETS DIRECTLY ALLOCATED TO THE LAST ROOM
		for pair in matchPairs:
			if len(pair)==1:
				byePair = pair
			else:
				availablePairs.append(pair)

		
		for previousRoom, previousPair in roomAssignments[matchKey - 1].items():

			if len(previousPair) == 1: # THE BYE PLAYER ALWAYS GOES TO THE LAST ROOM
				continue # SKIP ITERATION IF FINAL ROOM IS BYE				
			
			p1, p2 = previousPair
				
			wasntAny = []
			
			for currentPair in availablePairs:
				
				wasntP1 = p1 not in currentPair
				
				wasntP2 = p2 not in currentPair
				
				wasntAny.append(wasntP1 and wasntP2)
				
			filteredPairs = [pair for pair, ok in zip(availablePairs, wasntAny) if ok]
			
			if filteredPairs:
				selectedPair = filteredPairs[0] # ASSIGN THE FIRST COMPATIBLE PAIR
				shuffledPairs.append(selectedPair) 
				availablePairs.remove(selectedPair)
			else:
				break
					

		allPairs = shuffledPairs + availablePairs

		# Fallback if we couldn't assign all rooms uniquely, available
		if availablePairs: # Available pairs is not empty
			random.shuffle(allPairs)

		if byePair is not None: # IF A BYE PLAYER WAS REMOVED FOR CONFLICT FREE ALLOCATION
			allPairs.append(byePair) # REATTACH THE BYE PLAYER IN THE LAST POSITION

		roomMap = {room: pair for room, pair in zip(roomLabels, allPairs)}

		roomAssignments[matchKey] = roomMap
		
		# Terminal assignment
		terminalAssignments[matchKey] = {}
		for room, players in roomMap.items():
			t1, t2 = roomTerminals[room]
			if len(players) == 1:
				p1 = players[0]
				terminalAssignments[matchKey][p1] = t1
			else:
				p1, p2 = players	 
				terminalAssignments[matchKey][p1] = t1
				terminalAssignments[matchKey][p2] = t2

			
	return {
		'roomAssignments': roomAssignments,
		'terminalAssignments': terminalAssignments,
	}

# TURN PLAYER PAIRINGS INTO TERMINAL PAIRINGS

def matches_to_terminals(matches, terminalAssignments):
			
	matchesTerminals = {}

	for matchKey, matchValues in matches.items():
		matchesTerminals[matchKey] = []
		
		lookUpKey = matchKey + 2 # OFFSET BY NON PAIRED MATCHES (PRACTICE + AVATAR)

		for players in matchValues:
			if len(players) == 1:
				p1 = players[0]
				t1 = terminalAssignments[lookUpKey][p1]
				matchesTerminals[matchKey].append((t1,))
			else:
				p1, p2 = players
				t1 = terminalAssignments[lookUpKey][p1]
				t2 = terminalAssignments[lookUpKey][p2]
				matchesTerminals[matchKey].append((t1, t2))

	return matchesTerminals
			
# TURN TERMINAL PAIRINGS INTO ID IN SUBSESSION PAIRINGS

def matches_to_ids(matchesTerminals, label_to_id):
			
	matchesIDs = {}

	for matchKey, matchValues in matchesTerminals.items():
		matchesIDs[matchKey] = []

		for terminals in matchValues:
			if len(terminals) == 1:
				t1 = terminals[0]
				id1 = label_to_id[t1]
				matchesIDs[matchKey].append((id1,))
			else:
				t1, t2 = terminals
				id1 = label_to_id[t1]
				id2 = label_to_id[t2]
				matchesIDs[matchKey].append((id1, id2))

	return matchesIDs 

# GENERATE CONFLICT SEQUENCE

def draw_conflict_seq(Nrounds, sequenceManual, sequenceLabel, sessionID, totalSessions=60, baseSeed=12345):

	# A1: HL - HL - LH - LH - HL - HL - LH
	# A2: HL - HL - LH - HL - HL - LH - LH

	# B1: HL - LH - LH - HL - HL - LH - HL
	# B2: HL - LH - LH - HL - LH - HL - HL

	conflictSequences = {
		# --- TYPE A: Match 2 = HL ---
		# Practice (Match 1) = HL
		# A1 conflict sequence: H | H L L H H L
		"A1": {
			"conflict": (
				"high", "low",	# Practice (fixed HL)
				"high", "low",	# Match 2 (HL) AVATAR
				"low", "high",	# Match 3 (LH) F2F
				"low", "high",	# Match 4 (LH) F2F
				"high", "low",	# Match 5 (HL) F2F
			),
			# mapping: high -> full, low -> half
			"SIS": (
				"full", "half",	# Practice
				"full", "half",	# Match 2 
				"half", "full",	# Match 3 
				"half", "full",	# Match 4 
				"full", "half",	# Match 5 
			),
		},

		# Misma secuencia de conflicto que A1,
		# pero mapping invertido: high -> half, low -> full
		"A2": {
			"conflict": (
				"high", "low",	# Practice (fixed HL)
				"high", "low",	# Match 2 (HL) AVATAR
				"low", "high",	# Match 3 (LH) F2F
				"low", "high",	# Match 4 (LH) F2F
				"high", "low",	# Match 5 (HL) F2F
			),
			"SIS": (
				"half", "full",	# Practice
				"half", "full",	# Match 2
				"full", "half",	# Match 3
				"full", "half",	# Match 4
				"half", "full",	# Match 5
			),
		},

		# A2 original de conflicto: H | H L H H L L
		"A3": {
			"conflict": (
				"high", "low",	# Practice (fixed HL)
				"high", "low",	# Match 2 (HL) AVATAR
				"low", "high",	# Match 3 (LH) F2F
				"high", "low",	# Match 4 (HL) F2F
				"high", "low",	# Match 5 (HL) F2F
			),
			# mapping: high -> full, low -> half
			"SIS": (
				"full", "half",	# Practice
				"full", "half",	# Match 2
				"half", "full",	# Match 3
				"full", "half",	# Match 4
				"full", "half",	# Match 5
			),
		},

		# Misma A2 de conflicto, mapping invertido: high -> half, low -> full
		"A4": {
			"conflict": (
				"high", "low",	# Practice (fixed HL)
				"high", "low",	# Match 2 (HL) AVATAR
				"low", "high",	# Match 3 (LH) F2F
				"high", "low",	# Match 4 (HL) F2F
				"high", "low",	# Match 5 (HL) F2F
			),
			"SIS": (
				"half", "full",	# Practice
				"half", "full",	# Match 2
				"full", "half",	# Match 3
				"half", "full",	# Match 4
				"half", "full",	# Match 5
			),
		},

		# --- TYPE B: Match 2 = LH ---
		# Practice (Match 1) = HL
		# B1 conflict sequence: H | L L H H L H
		"B1": {
			"conflict": (
				"high", "low",	# Practice (fixed HL)
				"low", "high",	# Match 2 (LH) AVATAR
				"low", "high",	# Match 3 (LH) F2F
				"high", "low",	# Match 4 (HL) F2F
				"high", "low",	# Match 5 (HL) F2F
			),
			# mapping: high -> full, low -> half
			"SIS": (
				"full", "half",	# Practice
				"half", "full",	# Match 2
				"half", "full",	# Match 3
				"full", "half",	# Match 4
				"full", "half",	# Match 5
			),
		},

		# B1 conflicto, mapping invertido
		"B2": {
			"conflict": (
				"high", "low",	# Practice (fixed HL)
				"low", "high",	# Match 2 (LH) AVATAR
				"low", "high",	# Match 3 (LH) F2F
				"high", "low",	# Match 4 (HL) F2F
				"high", "low",	# Match 5 (HL) F2F
			),
			# mapping: high -> half, low -> full
			"SIS": (
				"half", "full",	# Practice
				"full", "half",	# Match 2
				"full", "half",	# Match 3
				"half", "full",	# Match 4
				"half", "full",	# Match 5
			),
		},

		# B2 conflict original: H | L L H L H H
		"B3": {
			"conflict": (
				"high", "low",	# Practice (fixed HL)
				"low", "high",	# Match 2 (LH) AVATAR
				"low", "high",	# Match 3 (LH) F2F
				"high", "low",	# Match 4 (HL) F2F
				"low", "high",	# Match 5 (LH) F2F
			),
			# mapping: high -> full, low -> half
			"SIS": (
				"full", "half",	# Practice
				"half", "full",	# Match 2
				"half", "full",	# Match 3
				"full", "half",	# Match 4
				"half", "full",	# Match 5
			),
		},

		# B2 conflicto, mapping invertido
		"B4": {
			"conflict": (
				"high", "low",	# Practice (fixed HL)
				"low", "high",	# Match 2 (LH) AVATAR
				"low", "high",	# Match 3 (LH) F2F
				"high", "low",	# Match 4 (HL) F2F
				"low", "high",	# Match 5 (LH) F2F
			),
			# mapping: high -> half, low -> full
			"SIS": (
				"half", "full",	# Practice
				"full", "half",	# Match 2
				"full", "half",	# Match 3
				"half", "full",	# Match 4
				"full", "half",	# Match 5
			),
		},
	}

	stepSequences = ["LSS", "SLL"]

	LSS = (
		"avatar", "avatar",	# Practice
		"avatar", "avatar",	# Match 2
		"medium", "large",	# Match 3
		"medium", "small",	# Match 4
		"medium", "small",	# Match 5
	)
	SLL = (
		"avatar", "avatar",	# Practice
		"avatar", "avatar",	# Match 2
		"medium", "small",	# Match 3
		"medium", "large",	# Match 4
		"medium", "large",	# Match 5
	)

	SEQUENCES = {}

	for label, value in conflictSequences.items():
			v1 = value.copy()
			v1["sliderSteps"] = LSS
			SEQUENCES[f"{label}-{stepSequences[0]}"] = v1

			v2 = value.copy()                 
			v2["sliderSteps"] = SLL
			SEQUENCES[f"{label}-{stepSequences[1]}"] = v2

	
	pilotSessions = 6

	# --- MANUAL MODE WITH SILENT FALLBACK ---
	if sequenceManual and sequenceLabel in SEQUENCES:
		label = sequenceLabel
		seq = SEQUENCES[sequenceLabel]
	else:
		try:
			sid = int(sessionID)
		except (TypeError, ValueError):
			sid = None

		if sid is not None and (pilotSessions < int(sessionID) <= totalSessions):
			keys = list(SEQUENCES.keys())
			master = []
			num_blocks = (totalSessions + len(keys) - 1) // len(keys)  # ceil(totalSessions/16)
			for k in range(num_blocks):
				rng = random.Random(baseSeed + k)
				block = keys.copy()
				rng.shuffle(block)
				master.extend(block)
			label = master[sid - pilotSessions - 1]
			seq = SEQUENCES[label]
		else: # fallback to random if label is not assigned or malformed
			label, seq = random.choice(list(SEQUENCES.items()))

	conflict = seq["conflict"]
	SIS = seq["SIS"]
	sliderSteps = seq["sliderSteps"]

	return label, conflict[:Nrounds], SIS[:Nrounds], sliderSteps[:Nrounds]

def drawTreatment(Nplayers):
	n_true = Nplayers // 2
	n_false = Nplayers // 2

	if Nplayers % 2 == 1:
		if random.random() < 0.5:
			n_true += 1
		else:
			n_false += 1

	assignments = [True]*n_true + [False]*n_false
	random.shuffle(assignments)
	return assignments