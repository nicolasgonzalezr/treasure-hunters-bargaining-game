# -*- coding: utf-8 -*-
"""
Created on Mon Jul  7 11:43:27 2025

@author: Usuario
"""

# scenes.py

# HOLDS ALL ELEMENTS TO BE DISPLAYED (WITH SCENE/CONDITION/PLAYER/ROUND SPECIFIC VARIANTS)
scene_components = {
	'background': 'global/{scenario}/background{room}.webp',
	'player_character': 'global/{scenario}/player_{room}_{player_gender}.gif',
	'opponent_character': 'global/{scenario}/opponent_{room}_{opponent_gender}.gif',
	'pouch_indicator': 'global/{scenario}/indicator_{pouch_status}.webp', # POUCH OR SHADOW
	'pouch_object': 'global/{scenario}/pouch_{room}_{pouch_present}.webp',
	'treasure': 'global/{scenario}/treasure_{treasure_status}.webp', # OPEN OR CLOSED
	'treasure_indicator': '{treasure_indicator}',
	'threat': 'global/{scenario}/threat_{threat_present}.gif',
	'dialogue_box': 'global/{scenario}/dialogue_{dialogue_status}.webp', # PLAYER OR OPPONENT
	'collapse': 'global/{scenario}/collapse_{collapse_present}.webp',
}

scene_dialogues = {
	'underwater': {
		1: '',
		2: '¡Al fin lo encontré! Ahí está <em>La Perla</em>, el naufragio de Barbanegra. ¡Qué suerte que traje mi bolsa!',
		3: 'Debo moverme rápido, ese buzo rojo me ha seguido hasta aquí. ¡Ahí hay una entrada!',
		4: '', # LOW CONFLICT, ROOM 2
		5: '¡Ese pulpo se ve peligroso!', # LOW CONFLICT, ROOM 2
		6: '', # LOW CONFLICT, ROOM 2
		7: '¡Se llevó mi bolsa! Tendré que llevar lo que encuentre en la mano... Se llevó la del otro buzo también.', # LOW CONFLICT, ROOM 2
		8: 'Al menos el camino se ve despejado, y parece haber otra habitación.', # LOW CONFLICT, ROOM 2
		9: '', # HIGH CONFLICT, ROOM 2
		10: 'Nada interesante por acá, pero parece haber otra habitación.', # HIGH CONFLICT, ROOM 2
		11: '',
		12: '¡Un cofre! A ver qué contiene...',
		13: '',
		14: '¡El tesoro perdido! Tomaré todo lo que pueda.',
		15: '¡Un momento! Este tesoro es mío.',
		16: '',
		17: '¡Se está derrumbando! ¡Tenemos que salir de aquí!',
		18: 'Si no llegamos a un acuerdo rápido, lo perderemos todo.',
		19: ''
	},
	'space': {
		1: '',
		2: 'La estación espacial <em>CRONOS-7</em>... Nadie sabe qué hacían acá ni por qué la abandonaron, pero dicen que los cristales del reactor son invaluables.',
		3: 'Debo moverme rápido, ese astronauta rojo me ha seguido hasta aquí. ¡Ahí está la entrada!',
		4: '', # LOW CONFLICT, ROOM 2
		5: '¡¿Qué es eso?!', # LOW CONFLICT, ROOM 2
		6: '', # LOW CONFLICT, ROOM 2
		7: '¡Se llevó mi bolsa! Tendré que llevar lo que encuentre en la mano... Se llevó la del otro astronauta también.', # LOW CONFLICT, ROOM 2
		8: 'Al menos el camino se ve despejado, y el reactor debe estar cerca.', # LOW CONFLICT, ROOM 2
		9: '', # HIGH CONFLICT, ROOM 2
		10: 'Parece ser un laboratorio, pero no veo cosas de valor. El reactor debe estar en la siguiente habitación.', # HIGH CONFLICT, ROOM 2
		11: '',
		12: '¡Ahí está el reactor! Creo que puedo desactivar la barrera...',
		13: '',
		14: 'Tomaré todos los cristales que pueda.',
		15: '¡Un momento! Este tesoro es mío.',
		16: '',
		17: '¡Va a explotar, se ha vuelto inestable sin el núcleo! ¡Tenemos que salir de aquí!',
		18: 'Si no llegamos a un acuerdo rápido, lo perderemos todo.',
		19: ''
	}
}

scene_buttons = {
	'underwater': {
		1: '',
		2: 'Siguiente',
		3: 'Entrar al barco hundido',
		4: '',
		5: '',
		6: '',
		7: 'Siguiente',
		8: 'Avanzar a la segunda habitación',
		9: '',
		10: 'Avanzar a la segunda habitación',
		11: '',
		12: 'Abrir cofre',
		13: '',
		14: 'Tomar el tesoro',
		15: 'Siguiente',
		16: '',
		17: 'Siguiente',
		18: 'Ir a negociación',
		19: ''
	},
	'space': {
		1: '',
		2: 'Siguiente',
		3: 'Entrar a la estación',
		4: '',
		5: '',
		6: '',
		7: 'Siguiente',
		8: 'Avanzar a la segunda habitación',
		9: '',
		10: 'Avanzar a la segunda habitación',
		11: '',
		12: 'Desactivar barrera',
		13: '',
		14: 'Tomar el tesoro',
		15: 'Siguiente',
		16: '',
		17: 'Siguiente',
		18: 'Ir a negociación',
		19: ''
	}
}

# FILLS SCENE SPECIFIC VALUES INTO COMPONENT PLACEHOLDERS, TAKES UNPACKED SCENE TEMPLATE AS ARGUMENT
def assemble_scene(
	scenario,
	room,
	player_gender,
	opponent_gender,
	pouch_status,
	pouch_present,
	treasure_status,
	treasure_indicator,
	threat_present,
	dialogue_status,
	collapse_present,
	sceneidx,
	auto_advance,
	timeout,
	conflict # DUMMY ARGUMENT, UNUSED BUT NEEDED TO UNPACK SCENE TEMPLATES DIRECTLY AS ARGUMENTS
):
	base = {}

	for key, value in scene_components.items():
		path = value.format(
			scenario=scenario,
			room=room,
			player_gender=player_gender,
			opponent_gender=opponent_gender,
			pouch_status=pouch_status,
			pouch_present=pouch_present,
			treasure_indicator=treasure_indicator,
			threat_present=threat_present,
			dialogue_status=dialogue_status,
			collapse_present=collapse_present,
			treasure_status=treasure_status
		)

		if "blank" not in path:
			base[key] = path

	base['sceneidx'] = sceneidx
	base['dialogue'] = scene_dialogues[scenario].get(sceneidx, '')
	base['button_text'] = scene_buttons[scenario].get(sceneidx, '')
	base['auto_advance'] = auto_advance
	base['timeout'] = timeout
			
	return base

# THIS DICT GETS UNPACKED AND PASSED AS ARGUMENT FOR ASSEMBLE SCENE FUN
# BLANKS GET FILTERED OUT IN ASSEMBLE SCENE
scene_templates = {
	# ROOM 1
	1: {
		'sceneidx':1,
		'scenario':'{scenario}', 
		'room':1, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'pouch',
		'pouch_present':'present',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'blank', 
		'collapse_present':'blank',
		'auto_advance':True,
		'timeout':2000,
		'conflict': 'all'
	},
	2: {
		'sceneidx':2,
		'scenario':'{scenario}', 
		'room':1, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'pouch',
		'pouch_present':'present',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'player', 
		'collapse_present':'blank',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'all'
	},
	3: {
		'sceneidx':3,
		'scenario':'{scenario}', 
		'room':1, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'pouch',
		'pouch_present':'present',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'player', 
		'collapse_present':'blank',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'all'
	},
	# ROOM 2
	4: {
		'sceneidx':4,
		'scenario':'{scenario}', 
		'room':2, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'pouch',
		'pouch_present':'present',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'present',
		'dialogue_status':'blank', 
		'collapse_present':'blank',
		'auto_advance':True,
		'timeout':2000,
		'conflict': 'low'
	},
	5: {
		'sceneidx':5,
		'scenario':'{scenario}', 
		'room':2, 
		'player_gender':'{player_gender}',
		'opponent_gender':'{opponent_gender}',
		'pouch_status':'pouch',
		'pouch_present':'present',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'present',
		'dialogue_status':'player',
		'collapse_present':'blank',
		'auto_advance':True,
		'timeout':2000,
		'conflict': 'low'
	},
	6: {
		'sceneidx':6,
		'scenario':'{scenario}', 
		'room':2, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'pouch', 
		'pouch_present':'present',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'present',
		'dialogue_status':'blank', 
		'collapse_present':'blank',
		'auto_advance':True,
		'timeout':2000, #CSS ANIMATION ADDS ADDITIONAL TIME OVER THIS
		'conflict': 'low'
	},
	7: {
		'sceneidx':7,
		'scenario':'{scenario}', 
		'room':2, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{player_gender}', 
		'pouch_status':'shadow',
		'pouch_present':'blank',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'player', 
		'collapse_present':'blank',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'low'
	},
	8: {
		'sceneidx':8,
		'scenario':'{scenario}', 
		'room':2, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'shadow',
		'pouch_present':'blank',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'player', 
		'collapse_present':'blank',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'low'
	},
	9: {
		'sceneidx':9,
		'scenario':'{scenario}', 
		'room':2, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'pouch',
		'pouch_present':'present',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'blank', 
		'collapse_present':'blank',
		'auto_advance':True,
		'timeout':2000,
		'conflict': 'high'
	},
	10: {
		'sceneidx':10,
		'scenario':'{scenario}', 
		'room':2, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'pouch',
		'pouch_present':'present',
		'treasure_status':'blank',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'player', 
		'collapse_present':'blank',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'high'
	},
	# ROOM 3
	11: {
		'sceneidx':11,
		'scenario':'{scenario}', 
		'room':3, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'closed',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'blank', 
		'collapse_present':'blank',
		'auto_advance':True,
		'timeout':2000,
		'conflict': 'all'
	},
	12: {
		'sceneidx':12,
		'scenario':'{scenario}', 
		'room':3, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'closed',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'player', 
		'collapse_present':'blank',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'all'
	},
	13: {
		'sceneidx':13,
		'scenario':'{scenario}', 
		'room':3, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'open',
		'treasure_indicator':'{treasure_indicator}',
		'threat_present': 'blank',
		'dialogue_status':'blank', 
		'collapse_present':'blank',
		'auto_advance':True,
		'timeout':2000,
		'conflict': 'all'
	},
	14: {
		'sceneidx':14,
		'scenario':'{scenario}', 
		'room':3, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'open',
		'treasure_indicator':'{treasure_indicator}',
		'threat_present': 'blank',
		'dialogue_status':'player', 
		'collapse_present':'blank',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'all'
	},
	15: {
		'sceneidx':15,
		'scenario':'{scenario}', 
		'room':3, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'open',
		'treasure_indicator':'{treasure_indicator}',
		'threat_present': 'blank',
		'dialogue_status':'opponent', 
		'collapse_present':'blank',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'all'
	},
	16: {
		'sceneidx':16,
		'scenario':'{scenario}', 
		'room':3, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'open',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'blank', 
		'collapse_present':'present',
		'auto_advance':True,
		'timeout':4000,
		'conflict': 'all'

	},
	17: {
		'sceneidx':17,
		'scenario':'{scenario}', 
		'room':3, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'open',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'player', 
		'collapse_present':'present',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'all'
	},
	18: {
		'sceneidx':18,
		'scenario':'{scenario}',
		'room':3,
		'player_gender':'{player_gender}',
		'opponent_gender':'{opponent_gender}',
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'open',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'player',
		'collapse_present':'present',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'all'
	},
	19: {
		'sceneidx':19,
		'scenario':'{scenario}', 
		'room':3, 
		'player_gender':'{player_gender}', 
		'opponent_gender':'{opponent_gender}', 
		'pouch_status':'{pouch_status}',
		'pouch_present':'{pouch_present}',
		'treasure_status':'open',
		'treasure_indicator':'blank',
		'threat_present': 'blank',
		'dialogue_status':'blank',
		'collapse_present':'present',
		'auto_advance':False,
		'timeout':0,
		'conflict': 'all'
	},
}