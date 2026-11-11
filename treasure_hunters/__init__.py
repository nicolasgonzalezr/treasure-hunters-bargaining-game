from otree.api import *
import json
from datetime import datetime, timezone, timedelta
import random
import re
from pathlib import Path
from .scenes import scene_templates, assemble_scene
from .rounds import get_match, generate_round_settings, generate_matches, assign_rooms, matches_to_terminals, matches_to_ids, draw_conflict_seq, terminalRooms, drawTreatment


class C(BaseConstants):
	NAME_IN_URL = 'treasure_hunters'
	PLAYERS_PER_GROUP = None # Leave blank, is set dynamically in creating session
	NUM_ROUNDS = 10 # Max number of rounds for a full session (6), the app trims as needed
	SURPLUS = 18000 # Conflict = 0.5, total bargain surplus
	RESTRICTION = 0.25 # Bilateral, Conflict = 0.22
	RESTRICTED_MAX = SURPLUS*(1 - RESTRICTION) 
	RESTRICTED_POOL = SURPLUS*(1 - 2*RESTRICTION) # Bilateral
	DEFAULT_STEPS = 40 # Must divide value and restricted evenly
	F2F_STEPS = {"small": 3, "medium": 9, "large": 15} # Must divide value and restricted evenly
	COST = 0 # Consider removing, with cost !=0 surplus is actually value, not surplus
	BARGAIN_TIMEOUT = 60
	KICKOFF = 3 # Seconds of countdown before round start
	F2F_KICKOFF = 10 # Seconds of countdown before round start
	TRANSPORTATION = 16000 # Base

class Subsession(BaseSubsession):
	conflict = models.StringField(initial=None, blank=True)
	SIS = models.StringField(initial=None, blank=True)
	sequenceLabel = models.StringField(initial=None, blank=True)
	matchType = models.StringField(initial=None, blank=True)
	matchNumber = models.IntegerField()
	hasMatch = models.BooleanField()
	sliderSteps = models.IntegerField(blank=True)
	scenario = models.StringField(initial=None, blank=True)
  
def creating_session(subsession):

	if subsession.round_number == 1:
		
		# ASSIGN MANUAL SESSION ID IF NOT EMPTY, FALLBACK TO SESSION CODE
		subsession.session.label = subsession.session.config.get('session_id') or subsession.session.code

		players = subsession.get_players()

		n = subsession.session.num_participants

		subsession.session.vars['roundSettings'] = generate_round_settings(n)

		subsession.session.vars['totalRounds'] = len(subsession.session.vars['roundSettings']) * 2

		subsession.session.vars['payoffRound'] = random.randint(3, subsession.session.vars['totalRounds']) #DISREGARD 2 FIRST PRACTICE ROUNDS

		matches, _ = generate_matches(n) # OMITTED OUTPUT ARE MATCHES INCLUDING BYE PLAYER LABEL
		
		subsession.session.vars['rooms'] = assign_rooms(matches)

		subsession.session.vars['matchesTerminals'] = matches_to_terminals(matches, subsession.session.vars['rooms']['terminalAssignments'])
		
		# RANDOMIZED TREATMENT ASSIGNMENT WITH MANUAL OVERRIDE FOR DEVELOPMENT
		if subsession.session.config.get('treatment_manual'):
			subsession.session.vars['treatment'] = {f'P{i}': subsession.session.config.get('treatment') for i in range(1, n + 1)}
		else:
			assignments = drawTreatment(n)
			subsession.session.vars['treatment'] = {f'P{i}': assignments[i-1] for i in range(1, n + 1)}
			
		subsession.sequenceLabel, subsession.session.vars['conflict'], subsession.session.vars['SIS'], subsession.session.vars['sliderSteps'] = draw_conflict_seq(
			subsession.session.vars['totalRounds'],
			subsession.session.config.get('sequence_manual'),
			subsession.session.config.get('sequence'),
			subsession.session.label
		)

		# LOAD AND DRAW AVATAR BARGAIN STRATEGY
		concessionsPath = Path(__file__).resolve().parent / 'data' / 'ConcessionSchedules.json'
		with concessionsPath.open(encoding='utf-8') as f:
			pool = json.load(f)

		random.shuffle(pool) # RANDOMIZE
		r1 = pool[:n]		# FIRST ROUND SCHEDULE
		r2 = pool[n:2*n]	 # SECOND ROUND SCHEDULE

		for p, s1, s2 in zip(players, r1, r2):
			p.participant.vars['avatarSchedule'] = { # ASSIGN ANY SCHEDULE TO ANY PARTICIPANT, FULLY RANDOM
				1: {
					'timestamps': s1['timestamps'],
					'totalConcessions': s1['totalConcessions'],
					'timeToEquilibrium': s1['timeToEquilibrium'],
				},
				2: {
					'timestamps': s2['timestamps'],
					'totalConcessions': s2['totalConcessions'],
					'timeToEquilibrium': s2['timeToEquilibrium'],
				},
			}

		#ASSIGN TERMINAL LABELS MANUALLY
		labels = [f'T{i}' for i in range(1, len(players) + 1)]
		for player, label in zip(players, labels):
			player.participant.label = label

		subsession.session.vars['label_to_id'] = {
			p.participant.label: p.id_in_subsession # PARTICIPANT IS THE TERMINAL
			for p in players
		}
		subsession.session.vars['matchesIDs'] = matches_to_ids(subsession.session.vars['matchesTerminals'], subsession.session.vars['label_to_id'])			
		
		#INITIALIZE PAYOFF DICT
		playerLabels = subsession.session.vars['rooms']['terminalAssignments'][1].keys()
		placeholderPayoffs = [None] * subsession.session.vars['totalRounds']
		subsession.session.vars['payoffDict'] = {label: placeholderPayoffs.copy() for label in playerLabels}

	# HANDLE NON SCHEDULED ROUNDS
	hasMatch = subsession.session.vars['totalRounds'] >= subsession.round_number

	subsession.hasMatch = hasMatch

	if hasMatch: # DO NOT POPULATE FIELDS IN REMAINDER ROUNDS

		matchKey, matchType = get_match(
			subsession.round_number,
			subsession.session.vars['roundSettings']
		) # type: ignore

		conflict = subsession.session.vars['conflict'][subsession.round_number - 1] # OFFSET BY ONE TO ACCOUNT FOR ZERO INDEX
		SIS = subsession.session.vars['SIS'][subsession.round_number - 1] # OFFSET BY ONE TO ACCOUNT FOR ZERO INDEX

		subsession.conflict = conflict
		subsession.SIS = SIS
		subsession.matchType = matchType
		subsession.matchNumber = matchKey
		"""
		print(
			f"[DEBUG] AAPA round={subsession.round_number}, "
			f"matchKey={matchKey}, matchType={matchType}, conflict={conflict}"
		)
		"""
		if matchType in ['practice', 'avatar']:
			# Solo play: each player is their own group
			solo_ids = [p.id_in_subsession for p in subsession.get_players()]
			matrix = [[i] for i in solo_ids]
			subsession.set_group_matrix(matrix)

		elif matchType == 'faceToFace':
			# Face-to-face matches: use the precomputed id pairings
			pairings = subsession.session.vars['matchesIDs'][matchKey-2]  # Offset (subtract) 2 to account for practice and avatar matches (not in the match dict)
			matrix = [list(t) for t in pairings]
			subsession.set_group_matrix(matrix)
			# GRAB STEP SIZE
			stepCondition = subsession.session.vars['sliderSteps'][subsession.round_number - 1]
			subsession.sliderSteps = C.F2F_STEPS.get(stepCondition, None)

		# Invert terminal assignments (currently P:T) to look for player seated at the terminal (T:P) in current match
		inverted = {v: k for k, v in subsession.session.vars['rooms']['terminalAssignments'][matchKey].items()}

		# Assign corresponding match player label, treatment condition and initial offers 
		for p in subsession.get_players():

			p.player_label = inverted[p.participant.label]
			p.experimental = subsession.session.vars['treatment'][p.player_label]

			if conflict == "high":
				p.player_offer = C.SURPLUS
				p.bot_offer = C.SURPLUS
			else:
				p.player_offer = C.RESTRICTED_MAX
				p.bot_offer = C.RESTRICTED_MAX

		# Scenario mapping by round number
		round_to_scenario = {
			1: 'space',
			2: 'underwater'
		}

		round_to_scenario[3] = 'space' if conflict == 'low' else 'underwater'
		round_to_scenario[4] = 'space' if conflict == 'low' else 'underwater'
			
		subsession.scenario =	round_to_scenario.get(subsession.round_number, 'underwater')

def vars_for_admin_report(subsession):
	session = subsession.session
	subsessions = session.get_subsessions()

	requests = {}

	for sub in subsessions:
		matchKey = sub.field_maybe_none('matchNumber')
		if matchKey is None:
			continue

		groups = {}
		nRound = sub.round_number

		for group in sub.get_groups():
			if group.advanceRequest:
				gid = group.id_in_subsession
				groups[gid] = {}
				groups[gid]["currentPage"] = group.requestAt
				rooms = session.vars['rooms']['terminalAssignments'][matchKey]
				groupPlayers = group.get_players()
				groups[gid]["participantCodes"] = [player.participant.code for player in groupPlayers]
				terminal = rooms[groupPlayers[0].player_label]
				groups[gid]["room"] = terminalRooms[terminal]

		if groups: 
			requests[nRound] = groups

	return dict(requests=requests)

# HELPER TO PASS TIMEOUT TO THE BARGAIN TIMER AT PAGE LOAD
def mmss(t):
	m = int(t // 60)
	s = int(t % 60)
	return f"{m:02d}:{s:02d}"

# HELPER TO FORMAT TO CHILEAN CURRENCY
def formatCLP(value):
	return "${:,}".format(value).replace(",", ".")

class Group(BaseGroup):
	round_start_time = models.StringField(initial=None, blank=True)
	convergence_time = models.StringField(initial=None, blank=True)
	timeoutAt = models.StringField(initial=None, blank=True)
	advanceRequest = models.BooleanField(initial=False)
	advanceGranted = models.BooleanField(initial=False)
	requestAt = models.StringField(initial=None, blank=True)
			
LIKERT_CHOICES = [
	[1, 'Totalmente en desacuerdo'],
	[2, 'En desacuerdo'],
	[3, 'Ni de acuerdo ni en desacuerdo'],
	[4, 'De acuerdo'],
	[5, 'Totalmente de acuerdo'],
]

LIKERT_POWER = [
	[1, 'Definitivamente <strong>el otro</strong>'],
	[2, 'Tal vez <strong>el otro</strong>'],
	[3, 'Neutral'],
	[4, 'Tal vez <strong>yo</strong>'],
	[5, 'Definitivamente <strong>yo</strong>'],
]

class Player(BasePlayer):

	player_label = models.StringField()
	opponent_label = models.StringField(blank=True)

	experimental = models.BooleanField() # TREATMENT BOOLEAN

	player_offer = models.CurrencyField(blank=True)

	opening_offer = models.CurrencyField(blank=True)

	AvatarSelectionID = models.StringField(blank=True)
	OpponentAvatarID = models.StringField(blank=True)

	bot_offer = models.CurrencyField(blank=True)
	total_concessions = models.IntegerField()
	time_to_equilibrium = models.FloatField()
			
	agreement_reached = models.BooleanField()
	round_payoff = models.CurrencyField(blank=True) # Round to round results
	round_selected = models.IntegerField(blank=True) # Round selected for payoff

#	dictator_share = models.CurrencyField()
#	fairness_share = models.CurrencyField()
#	reservation_share = models.CurrencyField()
			
	Beliefs_1 = models.IntegerField(
		choices=LIKERT_CHOICES,
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">El otro jugador estuvo dispuesto a ceder para llegar a un acuerdo.</span>'
		)
			
	Beliefs_2_R = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Al otro jugador sólo le preocupaba ganar, incluso a costa mía.</span>'
		)
			
	SIS_FD1 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">El modo en que nos comportamos en la última ronda tendrá consecuencias en las siguientes.</span>'
		)
			
	SIS_MD1 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Lo que hacía cada uno en la última ronda afectaba al otro.</span>'
		)
			
	SIS_C1_R = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Los dos conseguimos el resultado que queríamos.</span>'
		)
			
	SIS_FD2_R = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">El resultado de la última ronda no afectará cómo nos tratemos en el futuro.</span>'
		)
			
	SIS_MD2_R = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Nada de lo que hizo cada uno en la última ronda afectó al resultado del otro.</span>'
		)
			
	SIS_IC1 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Los dos sabíamos lo que quería el otro.</span>'
		)
			
	SIS_C2 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Había un conflicto entre lo que quería cada uno en la última ronda.</span>'
		)
			
	SIS_IC2_R = models.IntegerField(
		choices=LIKERT_CHOICES,
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">No creo que el otro haya sabido lo que yo quería.</span>'
		)
			
	SIS_P1 = models.IntegerField(
		choices=LIKERT_POWER, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">¿Quién de los dos crees que tuvo mayor control sobre su propio resultado?</span>'
		)
			
	SIS_P2_R = models.IntegerField(
		choices=LIKERT_POWER, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">¿Quién de los dos tuvo menos influencia en los resultados de la ronda?</span>'
		)
			
	previousRelation = models.StringField(
		choices=[
			[1, 'Nada'],
			[2, 'Muy poco'],
			[3, 'Algo'],
			[4, 'Bastante'],
			[5, 'Mucho']
		],
		widget=widgets.RadioSelectHorizontal,
		label='<span style="font-size:3.25vh; font-weight:bold;">¿Qué tan bien conocías a la persona con la que jugaste?</span>'
	)
			
	MC_1 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">El avatar del otro jugador me ayudó a entender mejor sus acciones durante la negociación.</span>'
		)

	MC_2 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Ver el avatar ayudó a que la interacción se sintiera más natural.</span>'
		)
			
	age = models.IntegerField(
		choices=list(range(18, 100)),
		label='<span style="font-size:3.25vh; font-weight:bold;">Edad</span>'
	)

	sex = models.StringField(
		choices=[
			"Mujer",
			"Hombre",
			"Intersexual",
			"Prefiero no responder"
		],
		label='<span style="font-size:3.25vh; font-weight:bold;">Sexo asignado al nacer:</span>'
	)

	gender = models.StringField(
		choices=[
			"Mujer",
			"Hombre",
			"No binario / Otro género",
			"Prefiero no responder"
		],
		label='<span style="font-size:3.25vh; font-weight:bold;">¿Con qué género te identificas?</span>'
	)

	ocupation = models.StringField(
		choices=[
			"Trabajando (ocupado/a)",
			"Buscando trabajo (cesante / desempleado/a)",
			"Estudiante",
			"Dueña/o de casa",
			"Jubilado/a o pensionado/a",
			"Incapacitado/a para trabajar",
			"Otra situación"
		],
		label='<span style="font-size:3.25vh; font-weight:bold;">¿Cuál es tu situación ocupacional actual?</span>'
	)

	studyDepartment = models.StringField(
    choices=[
        "Agropecuaria y ciencias forestales (p.ej. agronomía, veterinaria)",
        "Artes, arquitectura y diseño",
        "Ciencias básicas (p.ej. matemática, física, química, biología)",
        "Ciencias sociales y políticas (p.ej. sociología, ciencia política, antropología)",
        "Derecho",
        "Economía y negocios/administración (p.ej. ingeniería comercial, administración de empresas, contabilidad)",
        "Educación (pedagogías)",
        "Humanidades (p.ej. filosofía, historia)",
        "Ingeniería",
				"Psicología",
        "Salud (p.ej. medicina, enfermería, kinesiología)"
    ],
		blank=True,
		label='<span style="font-size:3.25vh; font-weight:bold;">¿En qué facultad o escuela estudias?</span>'
	)

	participantExperience = models.StringField(
		choices=[
			"0 (ninguno)",
			"1",
			"2-4",
			"5-9",
			"10 o más"
		],
		label='<span style="font-size:3.25vh; font-weight:bold;">¿En cuántos otros estudios como este has participado antes?</span>'
	)

	selfAttractiveness = models.IntegerField(
		choices=list(range(0, 11)),
		label='<span style="font-size:3.25vh; font-weight:bold;">En una escala del 0 al 10, ¿Qué tan actractivo/a te consideras físicamente?</span>'
	)

	MMQ_1 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Frecuentemente intento explicar lo que me está pasando.</span>'
		)
			
	MMQ_2 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy una persona impulsiva.</span>'
		)

	MMQ_3 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">A veces experimento cambios de ánimo que no puedo controlar.</span>'
		)
			
	MMQ_4 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy capaz de captar los aspectos más profundos de las personas que me rodean.</span>'
		)
			
	MMQ_5 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Me puedo conectar con el estado mental de los demás.</span>'
		)
			
	MMQ_6 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Para entender las acciones de los demás, es fundamental comprender lo que sienten.</span>'
		)
			
	MMQ_7 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">A veces siento que estoy perdiendo el control de mis emociones.</span>'
		)
			
	MMQ_8 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy capaz de reflexionar sobre mis acciones.</span>'
		)
			
	MMQ_9 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Relacionarme con otras personas me impide ser yo mismo/a.</span>'
		)
			
	MMQ_10 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Me interesa entender cómo funciona mi mente.</span>'
		)
			
	MMQ_11 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Puedo tolerar las frustraciones de la vida cotidiana.</span>'
		)
			
	MMQ_12 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Las personas no me entienden.</span>'
		)
			
	MMQ_13 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Es mejor tener cuidado con los demás.</span>'
		)
			
	MMQ_14 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy capaz de empatizar con otros cuando me cuentan algo.</span>'
		)
			
	MMQ_15 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Me asusta abrirme con los demás.</span>'
		)
			
	MMQ_16 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Reflexiono sobre lo que me pasa.</span>'
		) 

	MMQ_17 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Encuentro útil analizar mi comportamiento.</span>'
		)

	MMQ_18 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Suelo preguntarme por qué pasan las cosas.</span>'
		)
			
	MMQ_19 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Para mí las cosas son blancas o son negras.</span>'
		)
			
	MMQ_20 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">No confío en los demás.</span>'
		)
			
	MMQ_21 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy sensible a lo que le pasa a los demás.</span>'
		)
			
	MMQ_22 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Generalmente, puedo adaptarme a diferentes contextos sin dificultad.</span>'
		)
			
	MMQ_23 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">A veces tengo emociones contradictorias.</span>'
		)
			
	MMQ_24 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy capaz de resolver problemas difíciles cuando se me presentan en la vida.</span>'
		)
			
	MMQ_25 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy capaz de sobrellevar la carga emocional de situaciones estresantes.</span>'
		)
			
	MMQ_26 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Cuando siento una emoción intensa, puedo controlarla.</span>'
		)
			
	MMQ_27 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">La gente me abandona.</span>'
		)
			
	MMQ_28 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Puedo conectarme fácilmente con lo que piensan las otras personas.</span>'
		)
			
	MMQ_29 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Es mejor tener cuidado con los desconocidos.</span>'
		)
			
	MMQ_30 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy capaz de enfrentar situaciones difíciles.</span>'
		)
			
	MMQ_31 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Soy una persona que piensa en los demás.</span>'
		)
			
	MMQ_32 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Me gusta entender por qué ciertas cosas me pasan a mí.</span>'
		)
			
	MMQ_33 = models.IntegerField(
		choices=LIKERT_CHOICES, 
		widget=widgets.RadioSelectHorizontal, 
		label='<span style="font-size:3.25vh; font-weight:bold;">Algunas personas son la causa de mis problemas.</span>'
		)

class ActionLog(ExtraModel):		
	sessionID = models.StringField()
	roundNumber = models.IntegerField()
	groupID = models.IntegerField()
	player1ID = models.StringField()
	player2ID = models.StringField()

	offerPlayer1 = models.CurrencyField()
	offerPlayer2 = models.CurrencyField()
			
	relativeTime = models.FloatField()
	timestamp = models.StringField()

	actorID = models.StringField()

def custom_export(players):
	yield ['sessionID', 'roundNumber', 'groupID', 'player1ID', 'player2ID',
		   'offerPlayer1', 'offerPlayer2', 'relativeTime', 'timestamp', 'actorID']

	for log in ActionLog.filter():
		yield [
			log.sessionID,
			log.roundNumber,
			log.groupID,
			log.player1ID,
			log.player2ID,
			log.offerPlayer1,
			log.offerPlayer2,
			log.relativeTime,
			log.timestamp,
			log.actorID,
		]

class WaitForGroup(WaitPage):
	wait_for_all_groups = False
	title_text = "Espera"
	body_text = "Esperando al otro jugador."

	@staticmethod
	def is_displayed(player):
		isF2F = player.subsession.field_maybe_none('matchType') == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isF2F and notBye

class WaitForSession(WaitPage):
	wait_for_all_groups = True  # Global sync
	title_text = "Espera"
	body_text = "Esperando a los otros jugadores."

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isSingle = matchType in ['practice', 'avatar']

		previousRound = player.round_number - 1 
		previousSubsession = player.subsession.in_round(previousRound) if previousRound > 0 else None
		previousMatchType = previousSubsession.field_maybe_none('matchType') if previousSubsession is not None else None
		wasAvatar = previousMatchType == 'avatar'
		isF2F = matchType == 'faceToFace'

		return isSingle or (wasAvatar and isF2F)

	""""
	@staticmethod
	def after_all_players_arrive(subsession): 

		# --- DEBUG LOGGING: roundSettings + matchesTerminals ---
		print("\n==========================")
		print(f"[DEBUG] AFTER_ALL_PLAYERS_ARRIVE → Round {subsession.round_number}")

		rs = subsession.session.vars.get('roundSettings')
		mt = subsession.session.vars['rooms']['terminalAssignments']

		print("[DEBUG] roundSettings:", rs if rs is not None else "❌ NOT FOUND")
		print("[DEBUG] terminals:", mt if mt is not None else "❌ NOT FOUND")

		# Show shape of roundSettings per match
		if isinstance(rs, dict):
			print("[DEBUG] roundSettings keys:", list(rs.keys()))
			for k, v in rs.items():
				print(f"	match {k}: {v}")

		# Show matchTerminal entries
		if isinstance(mt, dict):
			print("[DEBUG] terminals keys:", list(mt.keys()))
			for k, v in mt.items():
				print(f"	match {k}: {v}")

		print("==========================\n")
		# ---------------------------------------------------------
		
		if subsession.round_number == 1:
			players = subsession.get_players()
			subsession.session.vars['label_to_id'] = {
				p.participant.label: p.id_in_subsession # PARTICIPANT IS THE TERMINAL
				for p in players
			}
			subsession.session.vars['matchesIDs'] = matches_to_ids(subsession.session.vars['matchesTerminals'], subsession.session.vars['label_to_id'])
			
			#INITIALIZE PAYOFF DICT
			playerLabels = subsession.session.vars['rooms']['terminalAssignments'][1].keys()
			subsession.session.vars['payoffDict'] = {label: [] for label in playerLabels}

		# HANDLE NON SCHEDULED ROUNDS
		hasMatch = subsession.session.vars['totalRounds'] >= subsession.round_number

		subsession.hasMatch = hasMatch

		if hasMatch: # DO NOT POPULATE FIELDS IN REMAINDER ROUNDS

			matchKey, matchType = get_match(
				subsession.round_number,
				subsession.session.vars['roundSettings']
			) # type: ignore

			conflict = subsession.session.vars['conflict'][subsession.round_number - 1] # OFFSET BY ONE TO ACCOUNT FOR ZERO INDEX
			SIS = subsession.session.vars['SIS'][subsession.round_number - 1] # OFFSET BY ONE TO ACCOUNT FOR ZERO INDEX

			subsession.conflict = conflict
			subsession.SIS = SIS
			subsession.matchType = matchType
			subsession.matchNumber = matchKey
			
			print(
				f"[DEBUG] AAPA round={subsession.round_number}, "
				f"matchKey={matchKey}, matchType={matchType}, conflict={conflict}"
			)
			
			if matchType in ['practice', 'avatar']:
				# Solo play: each player is their own group
				solo_ids = [p.id_in_subsession for p in subsession.get_players()]
				matrix = [[i] for i in solo_ids]
				subsession.set_group_matrix(matrix)

			elif matchType == 'faceToFace':
				# Face-to-face matches: use the precomputed id pairings
				pairings = subsession.session.vars['matchesIDs'][matchKey-2]  # Offset (subtract) 2 to account for practice and avatar matches (not in the match dict)
				matrix = [list(t) for t in pairings]
				subsession.set_group_matrix(matrix)

			# Invert terminal assignments (currently P:T) to look for player seated at the terminal (T:P) in current match
			inverted = {v: k for k, v in subsession.session.vars['rooms']['terminalAssignments'][matchKey].items()}

			# Assign corresponding match player label, treatment condition and initial offers 
			for p in subsession.get_players():

				p.player_label = inverted[p.participant.label]
				p.experimental = subsession.session.vars['treatment'][p.player_label]

				if conflict == "high":
					p.player_offer = C.SURPLUS
					p.bot_offer = C.SURPLUS
				else:
					p.player_offer = C.RESTRICTED_MAX
					p.bot_offer = C.RESTRICTED_MAX
				
				#ASSIGN FILTERABLE VALUE TO PLAYER PAYOFF IN BYE ROUND
				if matchType == 'faceToFace' and len(p.get_others_in_group()) == 0:
					subsession.session.vars['payoffDict'][p.player_label].append(None)


		# Scenario mapping by round number
		round_to_scenario = {
			1: 'underwater',
			2: 'underwater',
			3: 'underwater',
			4: 'underwater'
		}
		
		subsession.scenario = round_to_scenario.get(subsession.round_number, 'underwater')
	"""

class AvatarCache(Page):
	
	@staticmethod
	def is_displayed(player):
		return player.subsession.round_number == 1
			
	@staticmethod
	def js_vars(player):
		projectRoot = Path(__file__).resolve().parents[1]
		glbDir = projectRoot / '_static' / 'global' / 'avatars' / 'glb'
		glbList = [f.name for f in glbDir.iterdir() if f.suffix.lower() == '.glb']
		return dict(avatarNames=glbList)

class SwapSeats(Page):

	@staticmethod
	def is_displayed(player):
		isFirst = player.round_number == 1
		isF2F = player.subsession.field_maybe_none('matchType') == 'faceToFace'
		isOdd = player.round_number % 2 == 1
		return isFirst or (isF2F and isOdd)

	@staticmethod
	def js_vars(player: Player):

		matchKey = player.subsession.matchNumber

		invertedCurrent = {v: k for k, v in player.session.vars['rooms']['terminalAssignments'][matchKey].items()}
		currentPlayer = invertedCurrent[player.participant.label]

		if player.subsession.field_maybe_none('matchType') == 'faceToFace':
			invertedPrevious = {v: k for k, v in player.session.vars['rooms']['terminalAssignments'][matchKey - 1].items()}
			# GET LABEL OF PLAYERS ASSIGNED TO THIS TERMINAL IN THE CURRENT AND PREVIOUS ROUND
			if invertedPrevious[player.participant.label] != currentPlayer:
				previousPlayer = invertedPrevious[player.participant.label]
				nextTerminal = player.session.vars['rooms']['terminalAssignments'][matchKey][previousPlayer]
				nextRoom = terminalRooms[nextTerminal]
			else: # NONE IF ITS THE FIRST F2F MATCH
				previousPlayer = None
				nextRoom = None
				nextTerminal = None

		else: # IS FIRST ROUND, NO PREVIOUS ASSIGNMENT EXISTS
			previousPlayer = None
			nextRoom = None
			nextTerminal = None

		currentPlayerNum = currentPlayer.lstrip('P')
		previousPlayerNum = previousPlayer.lstrip('P') if previousPlayer is not None else previousPlayer

		isF2F = player.subsession.field_maybe_none('matchType') == "faceToFace"
		wasF2F = player.subsession.in_round(player.round_number - 1).field_maybe_none('matchType') == "faceToFace" if player.round_number > 1 else False
		
		return {
			"currentPlayer": currentPlayerNum,
			"previousPlayer": previousPlayerNum,
			"noPrevious": previousPlayer is None,
			"nextTerminal": nextTerminal.lstrip('T') if nextTerminal is not None else nextTerminal,
			"nextRoom": nextRoom,
			"firstF2F": isF2F and not wasF2F
		}

	@staticmethod
	def live_method(player, data):

		action = data.get('action', None)

		if action == 'ping':
			group = player.group

			if group.advanceGranted: # Exit if the other player has already won the race
				return None

			if player.participant.vars.get("advanceAllowed"): # The first player that pings sets the group variable
				group.advanceGranted = True

			if not group.advanceRequest:
				group.advanceRequest = True
				group.requestAt = "Swap Seats"
				#print("Requesting advance at Swap Seats.")

			if group.advanceGranted:
				#print("Advance is granted, broadcasting to group.")
				for p in group.get_players():
					p.participant.vars["advanceAllowed"] = False # Turn switch off
				group.advanceRequest = False
				return {0: dict(advance=True)}
			else:
				return None
		else:
			return None
		
	@staticmethod # Guard against race between players in groups, force all switches off
	def before_next_page(player: Player, timeout_happened):
		group = player.group

		if group.advanceGranted:
			group.advanceGranted = False
		
		if group.advanceRequest:
			group.advanceRequest = False
			group.requestAt = None
			#print("Residual request for group left over, turning switch off.")

		if player.participant.vars.get("advanceAllowed"):
			player.participant.vars["advanceAllowed"] = False
			#print(f"Residual permission for player {player.id_in_group} left over, turning switch off.")

class GeneralIntro(Page):

	@staticmethod
	def is_displayed(player):
		return player.round_number == 1
			
class BlockTwo(Page):

	@staticmethod
	def is_displayed(player):
		return player.round_number == 1

	@staticmethod
	def js_vars(player: Player):

		matchKey = player.subsession.matchNumber
		invertedCurrent = {v: k for k, v in player.session.vars['rooms']['terminalAssignments'][matchKey].items()}
		currentPlayer = invertedCurrent[player.participant.label]
		currentPlayerNum = currentPlayer.lstrip('P')

		return {
			"currentPlayer": currentPlayerNum
		}
			
	@staticmethod
	def live_method(player, data):

		action = data.get('action', None)

		if action == 'ping':
			group = player.group

			if group.advanceGranted: # Exit if the other player has already won the race
				return None

			if player.participant.vars.get("advanceAllowed"): # The first player that pings sets the group variable
				group.advanceGranted = True

			if not group.advanceRequest:
				group.advanceRequest = True
				group.requestAt = "Block Two"
				#print("Requesting advance at Block Two.")

			if group.advanceGranted:
				#print("Advance is granted, broadcasting to group.")
				for p in group.get_players():
					p.participant.vars["advanceAllowed"] = False # Turn switch off
				group.advanceRequest = False
				return {0: dict(advance=True)}
			else:
				return None
		else:
			return None
		
	@staticmethod # Guard against race between players in groups, force all switches off
	def before_next_page(player: Player, timeout_happened):
		group = player.group

		if group.advanceGranted:
			group.advanceGranted = False
		
		if group.advanceRequest:
			group.advanceRequest = False
			group.requestAt = None
			#print("Residual request for group left over, turning switch off.")

		if player.participant.vars.get("advanceAllowed"):
			player.participant.vars["advanceAllowed"] = False
			#print(f"Residual permission for player {player.id_in_group} left over, turning switch off.")

class RoundIntro(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isSingle = matchType in ['practice', 'avatar']
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isSingle or (isF2F and notBye)
			
	@staticmethod
	def vars_for_template(player: Player):
		
		scenario = player.subsession.scenario
				
		return {
			"title_path": 'global/cazadores_de_tesoros.webp',
			"subtitle_path": 'global/{}/subtitle.webp'.format(scenario),
			"background_path": 'global/{}/title_background.webp'.format(scenario),
			"background_cover_path": 'global/{}/title_background_cover.webp'.format(scenario),
			"isFirst": player.round_number==1
		}
			
	@staticmethod
	def js_vars(player: Player):
						
		return {
			"isFirst": player.round_number==1
		}

class AvatarSelection(Page):
			
	@staticmethod
	def is_displayed(player):
		return player.subsession.round_number == 3 #HARDCODED TO APPEAR EXACTLY ON THE FIRST AVATAR ROUND, MORE THAN 2 PRACTICE ROUNDS WILL BREAK THIS
			
	@staticmethod
	def js_vars(player):
		#GUARD AGAINST MISMATCH BETWEEN JPG'S AND GLB'S
		projectRoot = Path(__file__).resolve().parents[1]
		jpgDir = projectRoot / '_static' / 'global' / 'avatars' / 'jpg'
		glbDir = projectRoot / '_static' / 'global' / 'avatars' / 'glb'
		jpgList = [f.name for f in jpgDir.iterdir() if f.suffix.lower() == '.jpg']
		glbList = [f.name for f in glbDir.iterdir() if f.suffix.lower() == '.glb']
		vettedList = []
		for jpg in jpgList:
			match = re.search(r'avatar_(\d+)_', jpg)
			if not match:
				continue  # skip malformed filenames
			avatarID = match.group(1)

			# Build expected glb filename
			expectedBlueGLB = f'avatar_{avatarID}_blue.glb'
			expectedRedGLB = f'avatar_{avatarID}_red.glb'

			# Check if it exists
			if expectedBlueGLB in glbList and expectedRedGLB in glbList:
				vettedList.append(jpg)

		random.shuffle(vettedList)
		return dict(avatarNames=vettedList)

	@staticmethod
	def live_method(player, data):
		if 'AvatarID' in data:
			player.AvatarSelectionID = data['AvatarID']
#			print("Avatar ID received: ", data['AvatarID'])
			return {player.id_in_group: dict(ack='AvatarID')}
		else:
			print("Error, no avatar ID received")

	@staticmethod
	def before_next_page(player: Player, timeout_happened):

		if player.field_maybe_none('AvatarSelectionID') is None:
			player.AvatarSelectionID = str(random.choice(range(1, 54)))

class FaceTracking(Page):

	@staticmethod
	def is_displayed(player):
		return player.subsession.round_number == 3 #HARDCODED TO APPEAR EXACTLY ON THE FIRST AVATAR ROUND, MORE THAN 2 PRACTICE ROUNDS WILL BREAK THIS

	@staticmethod
	def js_vars(player):
		#BUILD NAME BASED ON SELECTED ID
		avatarID = player.field_maybe_none('AvatarSelectionID') if player.field_maybe_none('AvatarSelectionID') is not None else '1'
		avatarName=f'avatar_{avatarID}_blue.glb'
		return dict(avatarName=avatarName)

def get_scene_list(player: Player):
			
	scenes = []

	conflictHigh = player.subsession.conflict == "high"
	conflictLow = player.subsession.conflict == "low"

	for template in scene_templates.values():
		# FIRST STEP, FILL TEMPLATE PLACEHOLDERS WITH PLAYER, ROUND AND SESSION VALUES
		formatted = {
			k: v.format(
				scenario=player.subsession.scenario,
				pouch_status= 'pouch' if conflictHigh else 'shadow',
				pouch_present= 'present' if conflictHigh else 'blank',
				player_gender='male',
				opponent_gender='male',
				treasure_indicator="{}<br><span class='arrow'>&#9660;</span>".format(formatCLP(C.SURPLUS)),
			) if isinstance(v, str) else v
			for k, v in template.items()
		}
		if conflictLow and formatted['conflict']=="high": # FILTER HIGH CONFLICT SCENES
			continue
		elif conflictHigh and formatted['conflict']=="low": # FILTER LOW CONFLICT SCENES
			continue
		else:
			# SECOND STEP, FILL GENERAL COMPONENTS PATHS WITH SCENE SPECIFIC VALUES
			scenes.append(assemble_scene(**formatted))
		
	paths = set()

	for scene in scenes:
		for value in scene.values():
			if isinstance(value, str) and value.endswith(('.webp', '.gif')):
				paths.add(value)

	return scenes, list(paths)
			
class StoryPage(Page):

	@staticmethod
	def is_displayed(player):
		# FOR THE FIRST TWO MATCHES
		return player.subsession.field_maybe_none('matchType') in ["practice", "avatar"]
			
	@staticmethod
	def js_vars(player):
		scenes, paths = get_scene_list(player)
		return dict(scenes=scenes, paths=paths, scenario=player.subsession.scenario)

class StorySummary(Page):

	@staticmethod
	def is_displayed(player):
		isF2F = player.subsession.field_maybe_none('matchType') == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isF2F and notBye
	
	@staticmethod
	def js_vars(player):

		conflictHigh = player.subsession.conflict == "high"
		
		return {
			"conflictHigh": conflictHigh,
			"max": C.SURPLUS if conflictHigh else C.RESTRICTED_MAX
		}
	
class BargainInstructions(Page):

	@staticmethod
	def is_displayed(player):
		return player.subsession.field_maybe_none('matchType') == "practice"
		
	@staticmethod
	def vars_for_template(player: Player):

		restriction_percentage = f'{C.RESTRICTED_POOL/C.SURPLUS * 100}%'

		return {
			"conflict": player.subsession.conflict,
			"restriction_percentage": restriction_percentage
#			"timer": mmss(C.BARGAIN_TIMEOUT)
		}
			
	@staticmethod
	def js_vars(player: Player):

		conflictHigh = player.subsession.conflict == "high"

		template = scene_templates[19]

		# FIRST STEP, FILL TEMPLATE PLACEHOLDERS WITH PLAYER, ROUND AND SESSION VALUES
		formatted = {
			k: v.format(
				scenario=player.subsession.scenario,
				pouch_status= 'pouch' if conflictHigh else 'shadow',
				pouch_present= 'present' if conflictHigh else 'blank',
				player_gender='male',
				opponent_gender='male',
				treasure_indicator="{}<br><span class='arrow'>&#9660;</span>".format(formatCLP(C.SURPLUS)),
			) if isinstance(v, str) else v
			for k, v in template.items()
		}
		# SECOND STEP, FILL GENERAL COMPONENTS PATHS WITH SCENE SPECIFIC VALUES			
		scene = assemble_scene(**formatted)
			
		# Extract only needed images
		paths = [
			val for val in scene.values()
			if isinstance(val, str) and val.endswith(('.webp', '.gif'))
		]
			
		sliderStep = C.SURPLUS/C.DEFAULT_STEPS if conflictHigh else C.RESTRICTED_POOL/C.DEFAULT_STEPS

		return {
			"scene": scene,
			"paths": paths,
			"min_offer": C.COST,
			"max_offer": C.SURPLUS,
			"my_offer": int(player.player_offer),
			"opponent_offer": C.SURPLUS - int(player.bot_offer),
			"slider_step": sliderStep,
			"relative_max": int(player.player_offer), # ALREADY ENCODES RESTRICTION
			"conflict": player.subsession.conflict,
			"timeout_seconds": C.BARGAIN_TIMEOUT
		}
	
class InstructionsF2F(Page):

	@staticmethod
	def is_displayed(player):
		previousRound = player.round_number - 1 
		previousSubsession = player.subsession.in_round(previousRound) if previousRound > 0 else None
		previousMatchType = previousSubsession.field_maybe_none('matchType') if previousSubsession is not None else None
		wasAvatar = previousMatchType == 'avatar'
		isF2F = player.subsession.field_maybe_none('matchType') == 'faceToFace'
		return isF2F and wasAvatar

	@staticmethod
	def vars_for_template(player: Player):

		restriction_percentage = f'{C.RESTRICTED_POOL/C.SURPLUS * 100}%'

		return {
			"conflict": player.subsession.conflict,
			"restriction_percentage": restriction_percentage
		}
			
	@staticmethod
	def js_vars(player: Player):

		conflictHigh = player.subsession.conflict == "high"

		sliderSteps = C.F2F_STEPS["small"]
			
		stepSize = C.SURPLUS/sliderSteps if conflictHigh else C.RESTRICTED_POOL/sliderSteps

		return {
			"min_offer": C.COST,
			"max_offer": C.SURPLUS,
			"my_offer": int(player.player_offer),
			"opponent_offer": C.SURPLUS - int(player.bot_offer),
			"slider_step": stepSize,
			"relative_max": int(player.player_offer), # ALREADY ENCODES RESTRICTION
			"conflict": player.subsession.conflict,
			"timeout_seconds": C.BARGAIN_TIMEOUT
		}

class OpeningOffer(Page):

	@staticmethod
	def is_displayed(player):
		isF2F = player.subsession.field_maybe_none('matchType') == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isF2F and notBye
			
	@staticmethod
	def live_method(player, data):
		#print(f"📨 live_method triggered for {player.id_in_group()}, data = {data}")
		group = player.group
		maxOffer = C.SURPLUS if player.subsession.conflict=="high" else C.RESTRICTED_MAX
		minOffer = C.SURPLUS/2

		action = data.get('action')
		
		if action == 'update_offer':
			
			new_offer = data.get('offer')
			
			try:
				new_offer = int(float(new_offer))
				opponent = player.get_others_in_group()[0]
				opponent_offer = opponent.player_offer
				
				if new_offer < minOffer or maxOffer < new_offer:
					return {} # REJECT UPDATE
			
				player.player_offer = new_offer
				
				response = {
					p.id_in_group: dict(
						my_offer=p.player_offer,
						opponent_offer= C.SURPLUS - p.get_others_in_group()[0].player_offer,
					)
					for p in group.get_players()
				}
				
				return response
					
			except (TypeError, ValueError):
				return None
			
		return None
			
		
	@staticmethod
	def vars_for_template(player: Player):

		restriction_percentage = f'{C.RESTRICTED_POOL/C.SURPLUS * 100}%'

		return {
			"conflict": player.subsession.conflict,
			"restriction_percentage": restriction_percentage,
		}
			
	@staticmethod
	def js_vars(player: Player):
		
		conflictHigh = player.subsession.conflict == "high"

		opponent = player.get_others_in_group()[0]

		sliderSteps = player.subsession.sliderSteps if player.subsession.field_maybe_none("sliderSteps") is not None else C.DEFAULT_STEPS
			
		stepSize = C.SURPLUS/sliderSteps if conflictHigh else C.RESTRICTED_POOL/sliderSteps

		return {
			"conflict": player.subsession.conflict,
			"slider_step": stepSize,
			"min_offer": C.COST,
			"max_offer": C.SURPLUS,
			"my_offer": int(player.player_offer),
			"opponent_offer": C.SURPLUS - int(opponent.player_offer),
			"opponent_label": opponent.player_label.lstrip('P')
		}

	@staticmethod
	def before_next_page(player: Player, timeout_happened):
		group = player.group
		now = datetime.now(timezone.utc)

		player.opening_offer = player.player_offer

		p1 = group.get_player_by_id(1)
		p2 = group.get_player_by_id(2)

		ActionLog.create(
			sessionID=group.session.label,
			roundNumber=player.round_number,
			groupID=player.group.id_in_subsession,
			player1ID=p1.player_label,
			player2ID=p2.player_label,
			offerPlayer1=p1.player_offer,
			offerPlayer2=p2.player_offer,
			relativeTime=0.0,
			timestamp=now.isoformat(),
			actorID='opening'
		)

class BargainHandshake(Page):
			
	@staticmethod
	def is_displayed(player):
		isF2F = player.subsession.field_maybe_none('matchType') == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isF2F and notBye
	
	@staticmethod
	def live_method(player, data):

		action = data.get('action', None)

		if action == 'ping':
			group = player.group

			if group.advanceGranted: # Exit if the other player has already won the race
				return None

			if player.participant.vars.get("advanceAllowed"): # The first player that pings sets the group variable
				group.advanceGranted = True

			if not group.advanceRequest:
				group.advanceRequest = True
				group.requestAt = "Bargain Handshake"
				#print("Requesting advance at Bargain Handshake.")

			if group.advanceGranted:
				#print("Advance is granted, broadcasting to group.")
				for p in group.get_players():
					p.participant.vars["advanceAllowed"] = False # Turn switch off
				group.advanceRequest = False
				return {0: dict(advance=True)}
			else:
				return None
		else:
			return None

	@staticmethod # Guard against race between players in groups, force all switches off
	def before_next_page(player: Player, timeout_happened):
		group = player.group

		if group.advanceGranted:
			group.advanceGranted = False
		
		if group.advanceRequest:
			group.advanceRequest = False
			group.requestAt = None
			#print("Residual request for group left over, turning switch off.")

		if player.participant.vars.get("advanceAllowed"):
			player.participant.vars["advanceAllowed"] = False
			#print(f"Residual permission for player {player.id_in_group} left over, turning switch off.")

class BargainClose(Page):
			
	@staticmethod
	def is_displayed(player):
		isF2F = player.subsession.field_maybe_none('matchType') == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isF2F and notBye
			
	@staticmethod
	def live_method(player, data):

		action = data.get('action', None)

		if action == 'ping':
			group = player.group

			if group.advanceGranted: # Exit if the other player has already won the race
				return None

			if player.participant.vars.get("advanceAllowed"): # The first player that pings sets the group variable
				group.advanceGranted = True

			if not group.advanceRequest:
				group.advanceRequest = True
				group.requestAt = "Bargain Close"
				#print("Requesting advance at Bargain Close.")

			if group.advanceGranted:
				#print("Advance is granted, broadcasting to group.")
				for p in group.get_players():
					p.participant.vars["advanceAllowed"] = False # Turn switch off
				group.advanceRequest = False
				return {0: dict(advance=True)}
			else:
				return None
		else:
			return None
		
	@staticmethod # Guard against race between players in groups, force all switches off
	def before_next_page(player: Player, timeout_happened):
		group = player.group

		if group.advanceGranted:
			group.advanceGranted = False
		
		if group.advanceRequest:
			group.advanceRequest = False
			group.requestAt = None
			#print("Residual request for group left over, turning switch off.")

		if player.participant.vars.get("advanceAllowed"):
			player.participant.vars["advanceAllowed"] = False
			#print(f"Residual permission for player {player.id_in_group} left over, turning switch off.")

class WaitForAvatar(WaitPage):
	wait_for_all_groups = True  # Global sync
	title_text = "Espera"
	body_text = "Esperando al otro jugador para comenzar la negociación."

	@staticmethod
	def is_displayed(player: Player):
		matchType = player.subsession.field_maybe_none('matchType')
		isSingle = matchType in ['practice', 'avatar']
		return isSingle
			
	@staticmethod
	def after_all_players_arrive(subsession):
		matchType = subsession.field_maybe_none('matchType')
		round = subsession.round_number

		if matchType == "avatar":
			#ASSIGN OPPONENT AVATAR
			if round % 2 == 0: # SECOND AVATAR ROUND
				for p in subsession.get_players():
					prev = p.in_round(round - 1)
					p.AvatarSelectionID = prev.field_maybe_none('AvatarSelectionID') if prev.field_maybe_none('AvatarSelectionID') is not None else str(random.choice(range(1, 54)))
					p.OpponentAvatarID = prev.field_maybe_none('OpponentAvatarID') if prev.field_maybe_none('OpponentAvatarID') is not None else str(random.choice(range(1, 54)))
			else: # FIRST AVATAR ROUND
				players = subsession.get_players()
				players_by_id = {p.id_in_subsession: p for p in players}
				N = len(players)
				avatarAssignment = {
						(
								p.id_in_subsession % N + 1
								if N < 3
								else (p.id_in_subsession + 1) % N + 1
						): p.field_maybe_none('AvatarSelectionID')
						for p in players
				}
				for player_id, avatar in avatarAssignment.items():
					players_by_id[player_id].OpponentAvatarID = avatar if avatar is not None else str(random.choice(range(1, 54)))

		# SET INITIAL ACTION LOG AND ROUND START TIME
		rawTime = datetime.now(timezone.utc)
		now = (rawTime + timedelta(seconds=C.KICKOFF)).isoformat() # ADD KICKOFF OFFSET

		for group in subsession.get_groups():
			p1 = group.get_player_by_id(1)

			ActionLog.create(
				sessionID=group.session.label,
				roundNumber=group.round_number,
				groupID=p1.group.id_in_subsession,
				player1ID=p1.player_label,
				player2ID=matchType,
				offerPlayer1=p1.player_offer,
				offerPlayer2=p1.bot_offer,
				relativeTime=0.0,
				timestamp=now,
				actorID='system'
			)
			group.round_start_time = now

class WaitForF2F(WaitPage):
	wait_for_all_groups = False  # Per group sync
	title_text = "Espera"
	body_text = "Esperando al otro jugador para comenzar la negociación."

	@staticmethod
	def is_displayed(player: Player):
		matchType = player.subsession.field_maybe_none('matchType')
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isF2F and notBye
			
	@staticmethod
	def after_all_players_arrive(group: Group):		
		# SET INITIAL ACTION LOG AND ROUND START TIME
		rawTime = datetime.now(timezone.utc)
		now = (rawTime + timedelta(seconds=C.F2F_KICKOFF)).isoformat() # ADD KICKOFF OFFSET

		p1 = group.get_player_by_id(1)
		p2 = group.get_player_by_id(2)

		p1.opponent_label = p2.player_label
		p2.opponent_label = p1.player_label

		ActionLog.create(
			sessionID=group.session.label,
			roundNumber=group.round_number,
			groupID=p1.group.id_in_subsession,
			player1ID=p1.player_label,
			player2ID=p2.player_label,
			offerPlayer1=p1.player_offer,
			offerPlayer2=p2.player_offer,
			relativeTime=0.0,
			timestamp=now,
			actorID='system'
		)
		
		group.round_start_time = now

class BargainPractice(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the practice match
		return player.subsession.field_maybe_none('matchType') == 'practice'
			
	timeout_seconds = C.BARGAIN_TIMEOUT + C.KICKOFF

	@staticmethod
	def live_method(player, data):
		#print(f"📨 live_method triggered for {player.id_in_group()}, data = {data}")
		group = player.group
		now = datetime.now(timezone.utc)
		maxOffer = C.SURPLUS if player.subsession.conflict=="high" else C.RESTRICTED_MAX

		action = data.get('action')

		if action == 'ping':
			#print(f"📥 Ping received at {now}")
			convergence_str = group.field_maybe_none('convergence_time')
			if convergence_str:
				elapsed = (now - datetime.fromisoformat(convergence_str)).total_seconds()
				#print(f"⏳ Convergence started at {convergence_str}")
				#print(f"⏱ Elapsed: {elapsed:.2f} seconds")
				if elapsed >= 3:
				#	print("✅ Sending advance")
					return {
						p.id_in_group: dict(advance=True)
						for p in group.get_players()
					}
				  
		
		if action == 'update_offer':
			
			relative_time = (now - datetime.fromisoformat(group.round_start_time)).total_seconds()
			new_offer = data.get('offer')
			
			try:
				
				new_offer = int(new_offer)
				opponent_offer = player.bot_offer
				
				# CLAMP OFFER IF ITS SMALLER THAN THE OPPONENT'S OR IF IT EXCEEDS RESTRICTION
				if new_offer < (C.SURPLUS - opponent_offer) or maxOffer < new_offer:
					return {} # REJECT UPDATE
			
				player.player_offer = new_offer
				
				ActionLog.create(
					sessionID=group.session.label,
					roundNumber=player.round_number,
					groupID=player.group.id_in_subsession,
					player1ID=player.player_label,
					player2ID="practice",
					offerPlayer1=new_offer,
					offerPlayer2=opponent_offer,
					relativeTime=relative_time,
					timestamp=now.isoformat(),
					actorID=player.player_label
				)
				
				# Check for agreement condition
				offers_close = new_offer == (C.SURPLUS - opponent_offer)
				
				if offers_close:
					if group.field_maybe_none('convergence_time') is None:
						group.convergence_time = now.isoformat()
					agreement_close = True
				else:
					group.convergence_time = None
					agreement_close = False
					
				
				response = {
					p.id_in_group: dict(
						my_offer=int(p.player_offer),
						opponent_offer= C.SURPLUS - int(p.bot_offer),
						agreement_close=agreement_close
					)
					for p in group.get_players()
				}
				
				return response
					
			except (TypeError, ValueError):
				return None

		if action == 'avatar_offer':
			
			relative_time = (now - datetime.fromisoformat(group.round_start_time)).total_seconds()
			avatar_offer = data.get('offer')
			
			try:
				
				avatar_offer = int(avatar_offer)

				player_offer = player.player_offer
				
				if avatar_offer > player_offer: # CLAMP OFFER IF ITS LARGER THAN THE PLAYER'S
					return {} # REJECT UPDATE
			
				player.bot_offer = C.SURPLUS - avatar_offer

				ActionLog.create(
					sessionID=group.session.label,
					roundNumber=player.round_number,
					groupID=player.group.id_in_subsession,
					player1ID=player.player_label,
					player2ID="practice",
					offerPlayer1=player_offer,
					offerPlayer2=C.SURPLUS - avatar_offer,
					relativeTime=relative_time,
					timestamp=now.isoformat(),
					actorID="practice"
				)
				
				# Check for agreement condition
				offers_close = player_offer == avatar_offer
				
				if offers_close:
					if group.field_maybe_none('convergence_time') is None:
						group.convergence_time = now.isoformat()
					agreement_close = True
				else:
					group.convergence_time = None
					agreement_close = False
					
				
				response = {
					p.id_in_group: dict(
						my_offer=int(p.player_offer),
						opponent_offer= C.SURPLUS - int(p.bot_offer),
						agreement_close=agreement_close
					)
					for p in group.get_players()
				}
				
				return response
					
			except (TypeError, ValueError):
				return None
		
		return None

		
	@staticmethod
	def vars_for_template(player: Player):

		restriction_percentage = f'{C.RESTRICTED_POOL/C.SURPLUS * 100}%'

		return {
			"conflict": player.subsession.conflict,
			"restriction_percentage": restriction_percentage
#			"timer": mmss(C.BARGAIN_TIMEOUT)
		}
			
	@staticmethod
	def js_vars(player: Player):

		conflictHigh = player.subsession.conflict == "high"

		template = scene_templates[19]

		# FIRST STEP, FILL TEMPLATE PLACEHOLDERS WITH PLAYER, ROUND AND SESSION VALUES
		formatted = {
			k: v.format(
				scenario=player.subsession.scenario,
				pouch_status= 'pouch' if conflictHigh else 'shadow',
				pouch_present= 'present' if conflictHigh else 'blank',
				player_gender='male',
				opponent_gender='male',
				treasure_indicator="{}<br><span class='arrow'>&#9660;</span>".format(formatCLP(C.SURPLUS)),
			) if isinstance(v, str) else v
			for k, v in template.items()
		}
		# SECOND STEP, FILL GENERAL COMPONENTS PATHS WITH SCENE SPECIFIC VALUES			
		scene = assemble_scene(**formatted)
			
		# Extract only needed images
		paths = [
			val for val in scene.values()
			if isinstance(val, str) and val.endswith(('.webp', '.gif'))
		]
			
		sliderStep = C.SURPLUS/C.DEFAULT_STEPS if conflictHigh else C.RESTRICTED_POOL/C.DEFAULT_STEPS

		return {
			"scene": scene,
			"paths": paths,
			"min_offer": C.COST,
			"max_offer": C.SURPLUS,
			"my_offer": int(player.player_offer),
			"opponent_offer": C.SURPLUS - int(player.bot_offer),
			"slider_step": sliderStep,
			"relative_max": int(player.player_offer), # ALREADY ENCODES RESTRICTION
			"conflict": player.subsession.conflict,
			"timeout_seconds": C.BARGAIN_TIMEOUT,
			"kickOff": C.KICKOFF
		}
			
	@staticmethod
	def before_next_page(player: Player, timeout_happened):

		timeoutAt = player.group.field_maybe_none('timeoutAt')

		player.group.timeoutAt = datetime.now(timezone.utc).isoformat() if timeout_happened and timeoutAt is None else None

		offer_p1 = player.player_offer
		offer_p2 = C.SURPLUS - player.bot_offer
			
		agreement = offer_p1 == offer_p2
		player.agreement_reached = agreement
		
		if agreement:
			player.round_payoff = player.player_offer
		else:
			player.round_payoff = 0
		
		#APPEND RESULT TO PLAYER PAYOFF LIST
		player.session.vars['payoffDict'][player.player_label][player.round_number - 1] = player.round_payoff

class BargainAvatar(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the avatar match
		return player.subsession.field_maybe_none('matchType') == 'avatar'
			
	timeout_seconds = C.BARGAIN_TIMEOUT + C.KICKOFF

	@staticmethod
	def live_method(player, data):
		#print(f"📨 live_method triggered for {player.id_in_group()}, data = {data}")
		group = player.group
		now = datetime.now(timezone.utc)
		maxOffer = C.SURPLUS if player.subsession.conflict=="high" else C.RESTRICTED_MAX

		action = data.get('action')

		if action == 'ping':
			#print(f"📥 Ping received at {now}")
			convergence_str = group.field_maybe_none('convergence_time')
			if convergence_str:
				elapsed = (now - datetime.fromisoformat(convergence_str)).total_seconds()
				#print(f"⏳ Convergence started at {convergence_str}")
				#print(f"⏱ Elapsed: {elapsed:.2f} seconds")
				if elapsed >= 3:
				#	print("✅ Sending advance")
					return {
						p.id_in_group: dict(advance=True)
						for p in group.get_players()
					}
				  
		
		if action == 'update_offer':
			
			relative_time = (now - datetime.fromisoformat(group.round_start_time)).total_seconds()
			new_offer = data.get('offer')
			
			try:
				new_offer = int(new_offer)
				opponent_offer = player.bot_offer
				
				# CLAMP OFFER IF ITS SMALLER THAN THE OPPONENT'S OR IF IT EXCEEDS RESTRICTION
				if new_offer < (C.SURPLUS - opponent_offer) or maxOffer < new_offer:
					return {} # REJECT UPDATE
			
				player.player_offer = new_offer

				ActionLog.create(
					sessionID=group.session.label,
					roundNumber=player.round_number,
					groupID=player.group.id_in_subsession,
					player1ID=player.player_label,
					player2ID="avatar",
					offerPlayer1=new_offer,
					offerPlayer2=opponent_offer,
					relativeTime=relative_time,
					timestamp=now.isoformat(),
					actorID=player.player_label
				)
				
				# Check for agreement condition
				offers_close = new_offer == (C.SURPLUS - opponent_offer)
				
				if offers_close:
					if group.field_maybe_none('convergence_time') is None:
						group.convergence_time = now.isoformat()
					agreement_close = True
				else:
					group.convergence_time = None
					agreement_close = False
					
				
				response = {
					p.id_in_group: dict(
						my_offer=int(p.player_offer),
						opponent_offer= C.SURPLUS - int(p.bot_offer),
						agreement_close=agreement_close
					)
					for p in group.get_players()
				}
				
				return response
					
			except (TypeError, ValueError):
				return None

		if action == 'avatar_offer':
			
			relative_time = (now - datetime.fromisoformat(group.round_start_time)).total_seconds()
			avatar_offer = data.get('offer')
			
			try:
				
				avatar_offer = int(avatar_offer)

				player_offer = player.player_offer
				
				if avatar_offer > player_offer: # CLAMP OFFER IF ITS LARGER THAN THE PLAYER'S
					return {} # REJECT UPDATE
			
				player.bot_offer = C.SURPLUS - avatar_offer
				
				ActionLog.create(
					sessionID=group.session.label,
					roundNumber=player.round_number,
					groupID=player.group.id_in_subsession,
					player1ID=player.player_label,
					player2ID="avatar",
					offerPlayer1=player_offer,
					offerPlayer2=C.SURPLUS - avatar_offer,
					relativeTime=relative_time,
					timestamp=now.isoformat(),
					actorID="avatar"
				)

				# Check for agreement condition
				offers_close = player_offer == avatar_offer
				
				if offers_close:
					if group.field_maybe_none('convergence_time') is None:
						group.convergence_time = now.isoformat()
					agreement_close = True
				else:
					group.convergence_time = None
					agreement_close = False
					
				
				response = {
					p.id_in_group: dict(
						my_offer=int(p.player_offer),
						opponent_offer= C.SURPLUS - int(p.bot_offer),
						agreement_close=agreement_close
					)
					for p in group.get_players()
				}
				
				return response
					
			except (TypeError, ValueError):
				return None

		return None

		
	@staticmethod
	def vars_for_template(player: Player):

		restriction_percentage = f'{C.RESTRICTED_POOL/C.SURPLUS * 100}%'

		return {
			"conflict": player.subsession.conflict,
			"restriction_percentage": restriction_percentage
		}
			
	@staticmethod
	def js_vars(player: Player):

		conflictHigh = player.subsession.conflict == "high"

		template = scene_templates[19]

		# FIRST STEP, FILL TEMPLATE PLACEHOLDERS WITH PLAYER, ROUND AND SESSION VALUES
		formatted = {
			k: v.format(
				scenario=player.subsession.scenario,
				pouch_status= 'pouch' if conflictHigh else 'shadow',
				pouch_present= 'present' if conflictHigh else 'blank',
				player_gender='male',
				opponent_gender='male',
				treasure_indicator="{}<br><span class='arrow'>&#9660;</span>".format(formatCLP(C.SURPLUS)),
			) if isinstance(v, str) else v
			for k, v in template.items()
		}
		# SECOND STEP, FILL GENERAL COMPONENTS PATHS WITH SCENE SPECIFIC VALUES			
		scene = assemble_scene(**formatted)
			
		# Extract only needed images
		paths = [
			val for val in scene.values()
			if isinstance(val, str) and val.endswith(('.webp', '.gif'))
		]

		sched = player.participant.vars['avatarSchedule'][player.subsession.round_number - 2] # OFFSET BY TWO TO ACCOUNT FOR PRACTICE ROUNDS, KEYS ARE INT 1 AND 2
		player.total_concessions = sched['totalConcessions'] # RECORD AS CONTROL VARIABLE
		player.time_to_equilibrium = sched['timeToEquilibrium'] # RECORD AS CONTROL VARIABLE

		sliderStep = C.SURPLUS/C.DEFAULT_STEPS if conflictHigh else C.RESTRICTED_POOL/C.DEFAULT_STEPS
		
		return {
			"timeout_seconds": C.BARGAIN_TIMEOUT,
			"kickOff": C.KICKOFF,
			"conflict": player.subsession.conflict,
			"experimental": player.experimental,
			"slider_step": sliderStep,
			"concessionSchedule": sched['timestamps'],
			"scene": scene,
			"paths": paths,
			"min_offer": C.COST,
			"max_offer": C.SURPLUS,
			"my_offer": int(player.player_offer),
			"opponent_offer": C.SURPLUS - int(player.bot_offer),
			"match_type": player.subsession.matchType, # FOR BACKEND VIDEO LOGIC
			"session_id": player.session.label, # FOR BACKEND VIDEO LABEL
			"player_id": player.player_label, # FOR BACKEND VIDEO LABEL
			"round": player.subsession.round_number, # FOR BACKEND VIDEO LABEL,
			"roundStart": player.group.round_start_time, # FOR BACKEND INFERENCE LOGGING
			"avatarPath": f'avatar_{player.OpponentAvatarID}_red.glb'
		}
			
	@staticmethod
	def before_next_page(player: Player, timeout_happened):

		timeoutAt = player.group.field_maybe_none('timeoutAt')

		player.group.timeoutAt = datetime.now(timezone.utc).isoformat() if timeout_happened and timeoutAt is None else None

		offer_p1 = player.player_offer
		offer_p2 = C.SURPLUS - player.bot_offer
			
		agreement = offer_p1 == offer_p2
		player.agreement_reached = agreement
		
		if agreement:
			player.round_payoff = player.player_offer
		else:
			player.round_payoff = 0

		#APPEND RESULT TO PLAYER PAYOFF LIST
		player.session.vars['payoffDict'][player.player_label][player.round_number - 1] = player.round_payoff

class BargainF2F(Page):

	@staticmethod
	def is_displayed(player):
		isF2F = player.subsession.field_maybe_none('matchType') == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isF2F and notBye
			
	timeout_seconds = C.BARGAIN_TIMEOUT + C.F2F_KICKOFF
			
	@staticmethod
	def live_method(player, data):
		#print(f"📨 live_method triggered for {player.id_in_group()}, data = {data}")
		group = player.group
		now = datetime.now(timezone.utc)
		maxOffer = C.SURPLUS if player.subsession.conflict=="high" else C.RESTRICTED_MAX


		action = data.get('action')

		if action == 'ping':
			#print(f"📥 Ping received at {now}")
			convergence_str = group.field_maybe_none('convergence_time')
			if convergence_str:
				elapsed = (now - datetime.fromisoformat(convergence_str)).total_seconds()
				#print(f"⏳ Convergence started at {convergence_str}")
				#print(f"⏱ Elapsed: {elapsed:.2f} seconds")
				if elapsed >= 3:
				#	print("✅ Sending advance")
					return {
						p.id_in_group: dict(advance=True)
						for p in group.get_players()
					}
				  
		
		if action == 'update_offer':
			
			relative_time = (now - datetime.fromisoformat(group.round_start_time)).total_seconds()
			new_offer = data.get('offer')
			
			try:
				new_offer = int(new_offer)
				opponent = player.get_others_in_group()[0]
				opponent_offer = opponent.player_offer
				
				# CLAMP OFFER IF ITS SMALLER THAN THE OPPONENT'S OR IF IT EXCEEDS RESTRICTION
				if new_offer < (C.SURPLUS - opponent_offer) or maxOffer < new_offer:
					return {} # REJECT UPDATE
			
				player.player_offer = new_offer
				
				p1 = group.get_player_by_id(1)
				p2 = group.get_player_by_id(2)
				
				ActionLog.create(
					sessionID=group.session.label,
					roundNumber=player.round_number,
					groupID=player.group.id_in_subsession,
					player1ID=p1.player_label,
					player2ID=p2.player_label,
					offerPlayer1=p1.player_offer,
					offerPlayer2=p2.player_offer,
					relativeTime=relative_time,
					timestamp=now.isoformat(),
					actorID=player.player_label
				)

				# Check for agreement condition
				offers_close = p1.player_offer == (C.SURPLUS - p2.player_offer)
				
				if offers_close:
					if group.field_maybe_none('convergence_time') is None:
						group.convergence_time = now.isoformat()
					agreement_close = True
				else:
					group.convergence_time = None
					agreement_close = False
					
				
				response = {
					p.id_in_group: dict(
						my_offer=int(p.player_offer),
						opponent_offer= C.SURPLUS - int(p.get_others_in_group()[0].player_offer),
						agreement_close=agreement_close
					)
					for p in group.get_players()
				}
				
				return response
					
			except (TypeError, ValueError):
				return None
		return None
		
			
		
	@staticmethod
	def vars_for_template(player: Player):

		restriction_percentage = f'{C.RESTRICTED_POOL/C.SURPLUS * 100}%'

		return {
			"conflict": player.subsession.conflict,
			"restriction_percentage": restriction_percentage,
			"timer": mmss(C.BARGAIN_TIMEOUT)
		}
			
			
	@staticmethod
	def js_vars(player: Player):
		
		conflictHigh = player.subsession.conflict == "high"

		opponent = player.get_others_in_group()[0]

		sliderSteps = player.subsession.sliderSteps if player.subsession.field_maybe_none("sliderSteps") is not None else C.DEFAULT_STEPS

		stepSize = C.SURPLUS/sliderSteps if conflictHigh else C.RESTRICTED_POOL/sliderSteps

		return {
			"timeout_seconds": C.BARGAIN_TIMEOUT,
			"kickOff": C.F2F_KICKOFF,
			"conflict": player.subsession.conflict,
			"slider_step": stepSize,
			"min_offer": C.COST,
			"max_offer": C.SURPLUS,
			"my_offer": int(player.player_offer),
			"opponent_offer": C.SURPLUS - int(opponent.player_offer),
			"opponent_label": opponent.player_label.lstrip('P'),
			"match_type": player.subsession.matchType, # FOR BACKEND VIDEO LOGIC
			"session_id": player.session.label, # FOR BACKEND VIDEO LABEL
			"player_id": player.player_label, # FOR BACKEND VIDEO LABEL
			"round": player.subsession.round_number, # FOR BACKEND VIDEO LABEL,
			"round_start": player.group.round_start_time, # FOR BACKEND INFERENCE LOGGING
		}
			
	@staticmethod
	def before_next_page(player: Player, timeout_happened):

		timeoutAt = player.group.field_maybe_none('timeoutAt')

		# ERROR, FIELD GETS OVERWRITTEN TO NONE BY THE SECOND PLAYER IN THE GROUP!!!
		player.group.timeoutAt = datetime.now(timezone.utc).isoformat() if timeout_happened and timeoutAt is None else None

		group = player.group
		offer_p1 = group.get_player_by_id(1).player_offer
		offer_p2 = C.SURPLUS - group.get_player_by_id(2).player_offer
			
		agreement = offer_p1 == offer_p2
		player.agreement_reached = agreement
		
		if agreement:
			player.round_payoff = player.player_offer
		else:
			player.round_payoff = 0

		#APPEND RESULT TO PLAYER PAYOFF LIST
		player.session.vars['payoffDict'][player.player_label][player.round_number - 1] = player.round_payoff

class F2FResultsWait(WaitPage):
	wait_for_all_groups = False  # Group sync

	# This page ensures we can display the counterpart's gains for the round, even if one player's page advances faster and the result of the other has not been yet logged
	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isF2F and notBye

class Results(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isSingle = matchType in ['practice', 'avatar']
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		return isSingle or (isF2F and notBye)
			
	@staticmethod
	def js_vars(player: Player):

		matchType = player.subsession.field_maybe_none('matchType')
		isSingle = matchType in ['practice', 'avatar']

		if isSingle and player.agreement_reached:
			opponentPayoff = player.bot_offer
		elif isSingle:
			opponentPayoff = 0
		else:
			opponentPayoff = player.get_others_in_group()[0].round_payoff

		return dict(
			agreement_reached=player.agreement_reached,
			payoff=formatCLP(player.round_payoff),
			opponentPayoff=formatCLP(opponentPayoff)
		)

class Beliefs(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isAvatar = matchType == 'avatar'
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		isFull = player.subsession.field_maybe_none('SIS') == "full"
		return isFull and (isAvatar or (isF2F and notBye))
			
	form_model = 'player'
	form_fields = ['Beliefs_1', 'Beliefs_2_R']
			
class FullSIS1(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isAvatar = matchType == 'avatar'
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		isFull = player.subsession.field_maybe_none('SIS') == "full"
		return isFull and (isAvatar or (isF2F and notBye))
			
	form_model = 'player'
	form_fields = ['SIS_FD1', 'SIS_MD1']

class FullSIS2(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isAvatar = matchType == 'avatar'
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		isFull = player.subsession.field_maybe_none('SIS') == "full"
		return isFull and (isAvatar or (isF2F and notBye))
			
	form_model = 'player'
	form_fields = ['SIS_C1_R', 'SIS_FD2_R']
			
class FullSIS3(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isAvatar = matchType == 'avatar'
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		isFull = player.subsession.field_maybe_none('SIS') == "full"
		return isFull and (isAvatar or (isF2F and notBye))
			
	form_model = 'player'
	form_fields = ['SIS_MD2_R', 'SIS_IC1']

class FullSIS4(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isAvatar = matchType == 'avatar'
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		isFull = player.subsession.field_maybe_none('SIS') == "full"
		return isFull and (isAvatar or (isF2F and notBye))
			
	form_model = 'player'
	form_fields = ['SIS_C2', 'SIS_IC2_R']
			
class FullSIS5(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isAvatar = matchType == 'avatar'
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		isFull = player.subsession.field_maybe_none('SIS') == "full"
		return isFull and (isAvatar or (isF2F and notBye))
			
	form_model = 'player'
			
	@staticmethod
	def get_form_fields(player):
		isSecondF2F = player.subsession.field_maybe_none('matchType') == "faceToFace" and player.round_number % 2 == 0
		fields = ['SIS_P1', 'SIS_P2_R']
		if isSecondF2F:
			fields.append('previousRelation') #ONLY FOR SECOND F2F ROUNDS
		return fields
			
	@staticmethod
	def vars_for_template(player: Player):

		isSecondF2F = player.subsession.field_maybe_none('matchType') == "faceToFace" and player.round_number % 2 == 0

		return {
			"isSecondF2F": isSecondF2F
		}
			
class HalfSIS1(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isAvatar = matchType == 'avatar'
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		isHalf = player.subsession.field_maybe_none('SIS') == "half"
		return isHalf and (isAvatar or (isF2F and notBye))
			
	form_model = 'player'
	form_fields = ['SIS_C1_R', 'SIS_IC1']
			
class HalfSIS2(Page):

	@staticmethod
	def is_displayed(player):
		matchType = player.subsession.field_maybe_none('matchType')
		isAvatar = matchType == 'avatar'
		isF2F = matchType == 'faceToFace'
		notBye = len(player.get_others_in_group()) == 1 #SKIP BYES
		isHalf = player.subsession.field_maybe_none('SIS') == "half"
		return isHalf and (isAvatar or (isF2F and notBye))
			
	form_model = 'player'
			
	@staticmethod
	def get_form_fields(player):
		isSecondF2F = player.subsession.field_maybe_none('matchType') == "faceToFace" and player.round_number % 2 == 0
		fields = ['SIS_C2', 'SIS_IC2_R']
		if isSecondF2F:
			fields.append('previousRelation') #ONLY FOR SECOND F2F ROUNDS
		return fields
			
	@staticmethod
	def vars_for_template(player: Player):

		isSecondF2F = player.subsession.field_maybe_none('matchType') == "faceToFace" and player.round_number % 2 == 0

		return {
			"isSecondF2F": isSecondF2F
		}

class ManipulationCheck(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the last avatar round
		return player.subsession.field_maybe_none('matchType') == "avatar" and player.round_number % 2 == 0

	form_model = 'player'
	form_fields = ['MC_1', 'MC_2']

class PayoffRoulette(Page):

	@staticmethod
	def is_displayed(player):
		# ON THE SECOND PRACTICE ROUND AS A RANDOMIZED INCENTIVE INSTRUCTION
		isPractice = player.subsession.field_maybe_none('matchType') == 'practice' and player.round_number % 2 == 0
		# ON THE FINAL ROUND
		isFinal = player.session.vars['totalRounds'] == player.round_number
		return isPractice or isFinal

	@staticmethod
	def js_vars(player: Player):
		isFinal = player.session.vars['totalRounds'] == player.round_number
		isPractice = player.subsession.field_maybe_none('matchType') == 'practice'

		"""
		payoff_dict = player.session.vars.get('payoffDict', None)
		print("=== DEBUG payoffDict ===")
		print(payoff_dict)
		print("========================")
		"""

		results = player.session.vars['payoffDict'][player.player_label]
		selected = player.session.vars['payoffRound']

		isTest = all(r is None for r in results)

		if isTest: #NO MATCHES HAVE BEEN PLAYED
			payoffList = [6000, 0, 18000, 500, 20000, 10000] #DUMMY TESTING LIST
			payoffLabels = [f'Ronda {round}: {formatCLP(payoff)}' for round, payoff in enumerate(payoffList, start=1)]
			payoffIndex = random.randint(0, len(payoffList)-1)
			payoffRound = payoffIndex + 1
		
		elif isFinal and results[selected - 1] is not None: # PAYOFF EXISTS, PLAYER WAS NOT BYE IN THE SELECTED ROUND
			payoffList = [result for result in results[2:] if result is not None]
			payoffDict = {
				round: payoff for round, payoff in enumerate(results[2:], start=3) if payoff is not None 
			}
			payoffLabels = [f'Ronda {round}: {formatCLP(payoff)}' for round, payoff in payoffDict.items()]
			payoffIndex = selected - 3 # SUBTRACT 1 TO TURN INTO INDEX, THEN 2 TO MATCH THE INDICES OF THE SLICED PAYOFFS
			keys = list(payoffDict.keys())
			payoffIndex = keys.index(selected)
			payoffRound = selected
		
		elif isFinal and results[selected - 1] is None: # PAYOFF DOES NOT EXIST, PLAYER WAS BYE IN THE SELECTED ROUND
			payoffList = [result for result in results[2:] if result is not None]
			payoffDict = {
				round: payoff for round, payoff in enumerate(results[2:], start=3) if payoff is not None 
			}
			payoffLabels = [f'Ronda {round}: {formatCLP(payoff)}' for round, payoff in payoffDict.items()]
			payoffIndex = random.randint(0, len(payoffList)-1)
			keys = list(payoffDict.keys())
			payoffRound = keys[payoffIndex]

		else: # IS PRACTICE
			payoffList = [result for result in results if result is not None]
			payoffDict = {
				round: payoff for round, payoff in enumerate(results, start=1) if payoff is not None 
			}
			payoffLabels = [f'Ronda {round}: {formatCLP(payoff)}' for round, payoff in payoffDict.items()]
			payoffIndex = random.randint(0, len(payoffList)-1)
			keys = list(payoffDict.keys())
			payoffRound = keys[payoffIndex]

		if isFinal:	
			#FINAL VALUE ASSIGNMENT CORRESPONDS TO LAST ROULLETTE ONLY
			player.payoff = payoffList[payoffIndex]
			player.round_selected = int(payoffRound)

		return dict(
			isPractice = isPractice,
			transportation = C.TRANSPORTATION,
			payoffList = payoffList,
			payoffLabels = payoffLabels,
			payoffIndex = payoffIndex,
			payoffRound=int(payoffRound)
		)

# FIRST BLOCK QUESTIONNAIRES
class Demographic1(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['age', 'sex', 'gender']

class Demographic2(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1
			
	form_model = 'player'
	form_fields = ['ocupation', 'studyDepartment', 'participantExperience', 'selfAttractiveness']

class MMQ1(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_1', 'MMQ_2']

class MMQ2(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_3', 'MMQ_4', 'MMQ_5', 'MMQ_6']
			
class MMQ3(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_7', 'MMQ_8', 'MMQ_9', 'MMQ_10']

class MMQ4(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_11', 'MMQ_12', 'MMQ_13', 'MMQ_14']
			
class MMQ5(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_15', 'MMQ_16', 'MMQ_17', 'MMQ_18']

class MMQ6(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_19', 'MMQ_20', 'MMQ_21', 'MMQ_22']
			
class MMQ7(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_23', 'MMQ_24', 'MMQ_25', 'MMQ_26']

class MMQ8(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_27', 'MMQ_28', 'MMQ_29', 'MMQ_30']

class MMQ9(Page):

	@staticmethod
	def is_displayed(player):
		# Only for the first round
		return player.round_number == 1

	form_model = 'player'
	form_fields = ['MMQ_31', 'MMQ_32', 'MMQ_33']


page_sequence = [
	WaitForSession,
	AvatarCache,
	SwapSeats,
	GeneralIntro,
	Demographic1,
	Demographic2,
	MMQ1,
	MMQ2,
	MMQ3,
	MMQ4,
	MMQ5,
	MMQ6,
	MMQ7,
	MMQ8,
	MMQ9,
	BlockTwo,
	AvatarSelection, 
	FaceTracking,
	RoundIntro, 
	StoryPage,
	StorySummary,
	BargainInstructions,
	InstructionsF2F,
	OpeningOffer,
	WaitForGroup,
	BargainHandshake,
	WaitForAvatar,
	WaitForF2F,
	BargainPractice, 
	BargainAvatar,
	BargainF2F,
	F2FResultsWait,
	Results,
	WaitForGroup,
	BargainClose,
	Beliefs,
	FullSIS1,
	FullSIS2,
	FullSIS3,
	FullSIS4,
	FullSIS5,
	HalfSIS1,
	HalfSIS2,
	ManipulationCheck,
	PayoffRoulette
]

"""
# OVERWRITE FOR TESTING
page_sequence = [
	WaitForSession,
	AvatarSelection,
	WaitForAvatar,
	BargainAvatar
]


# OVERWRITE FOR TESTING
page_sequence = [
	WaitForSession,
	SwapSeats,
	StorySummary,
	InstructionsF2F,
	OpeningOffer,
	WaitForGroup,
	BargainHandshake,
	WaitForF2F,
	BargainF2F,
	F2FResultsWait,
	WaitForGroup,
	BargainClose
]

# Short version, omitting questionnaire and instructions
page_sequence = [
	WaitForSession,
	AvatarCache,
	SwapSeats,
	AvatarSelection, 
	FaceTracking,
	RoundIntro, 
	StoryPage,
	StorySummary,
	InstructionsF2F,
	OpeningOffer,
	WaitForGroup,
	BargainHandshake,
	WaitForAvatar,
	WaitForF2F,
	BargainPractice,
	BargainAvatar,
	BargainF2F,
	F2FResultsWait,
	Results,
	WaitForGroup,
	BargainClose,
	Beliefs,
	FullSIS1,
	FullSIS2,
	FullSIS3,
	FullSIS4,
	FullSIS5,
	HalfSIS1,
	HalfSIS2,
	ManipulationCheck,
	PayoffRoulette
]
"""