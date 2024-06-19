'''
TODO:
    * Figure out how to initiate multiple keyboard handlers asynchronously (while another is held down)
    * Make the G-force patterns only kick in after an input is held for a bit and gradually increase in strength from softer
    * Make the rails delay longer
'''

from time import sleep
from bhaptics import better_haptic_player as player
from bhaptics.better_haptic_player import BhapticsPosition
import keyboard
import os
from os import listdir
from os.path import isfile, join
from tail import Tail
import re
from threading import Thread

num_fire_groups = 0
current_fire_group_idx = 0
primary_fire_pattern_specs = []
secondary_fire_pattern_specs = []

def play(pattern_name, hotkey=None, charge_duration_millis=None, repeat_intervial_millis=None):
    print('Preparing', pattern_name)
    
    # If a charge time is configured, only proceed if the hotkey is held for the full charge duration.
    if charge_duration_millis:
        charged = False
        for t in range(int(charge_duration_millis / 50)):
            sleep(0.05)
            if not keyboard.is_pressed(hotkey):
                return
        if charged:
            print('Executing', pattern_name)
            player.submit_registered(pattern_name)
    
    # If repeat is configured, repeat pattern as long as the hotkey is held.
    if not repeat_intervial_millis:
        print('Executing', pattern_name)
        player.submit_registered(pattern_name)
    else:
        while keyboard.is_pressed(hotkey):
            player.submit_registered(pattern_name)
            sleep(repeat_intervial_millis / 1000.0)

def play_primary_fire(hotkey):
    #print('A) ', primary_fire_pattern_specs) #debug
    #print(f'A) current_fire_group_idx: {current_fire_group_idx}') #debug
    pattern_name, charge_millis, repeat_millis = primary_fire_pattern_specs[current_fire_group_idx]
    play(pattern_name, hotkey, charge_millis, repeat_millis)

def play_secondary_fire(hotkey):
    pattern_name, charge_millis, repeat_millis = secondary_fire_pattern_specs[current_fire_group_idx]
    play(pattern_name, hotkey, charge_millis, repeat_millis)

def update_fire_group(delta):
    global current_fire_group_idx
    current_fire_group_idx = (current_fire_group_idx + delta) % num_fire_groups
    print(f'New Fire Group {current_fire_group_idx+1}/{num_fire_groups}')
    #print('B) ', primary_fire_pattern_specs) #debug
    #print(f'B) current_fire_group_idx: {current_fire_group_idx}') #debug

def play_damage_if_happening(log_entry):
    if '"ShieldsUp":false' in log_entry:
        play('Shield Down VestArms', None, None, None)
    
    if re.search('(HullDamage|UnderAttack)', log_entry):
        play('Taking Damage VestArms', None, None, None)

def listen_for_journal_entries(path):
    t = Tail(path)
    t.register_callback(play_damage_if_happening)
    t.follow(s=0.25)

def listen_for_journal_entries_and_watch_journals():
    journals_path = 'C:\\Users\\std00\\Saved Games\\Frontier Developments\\Elite Dangerous'
    latest_journal_path = None
    daemon = None
    
    # Switch the journal listener to the new most recent journal file just in case this is
    # before the "current" one is created for a session or if this program runs across sessions.
    while(True):
        files = listdir(journals_path)
        paths = [join(journals_path, basename) for basename in files if re.search('^Journal\.', basename)]
        new_latest_journal_path = max(paths, key=os.path.getctime)
        
        if new_latest_journal_path != latest_journal_path:
            print(f'Detected new journal file! Switching to {new_latest_journal_path}')
            latest_journal_path = new_latest_journal_path
            if daemon is not None:
                print('Initiating daemon shutdown.')
                daemon.terminate()
                daemon.join()
                print('Daemon completed shutdown.')
            daemon = Thread(target=(lambda path=latest_journal_path : listen_for_journal_entries(path)))
            daemon.setDaemon(True)
            print('Starting new journal listener...')
            daemon.start()
        sleep(60)

def run_log_listener_daemon():
    daemon = Thread(target=listen_for_journal_entries_and_watch_journals)
    daemon.setDaemon(True)
    daemon.start()

def run():
    print("Press ctrl+z+enter to quit")
    keyboard.wait('ctrl+z+enter')
    os._exit(0)

if __name__ == "__main__":
    player.initialize()
    #print('C) ', primary_fire_pattern_specs) #debug
    #print(f'C) current_fire_group_idx: {current_fire_group_idx}') #debug
    
    # Configure log listener
    run_log_listener_daemon()
    
    # Configure preset flight bindings as defined in Joystick Gremlin
    # Joystick inputs should leverage Map to Keyboard actions with a Virtual Button condition for [0.95,1.0] and [-1.0,-0.95] ranges respectively.
    # Button inputs should leverage a simple Map to Keyboard action.
    keys_for_actions = {'Pitch Up':'*+a',
    'Pitch Down':'*+b',
    'Roll Right':'*+c',
    'Roll Left':'*+d',
    #'Thrust Up':'*+e', # The thrust inputs aren't usually the type of thing you want to trigger a g-force haptic pattern, so disabling for now.
    #'Thrust Down':'*+f',
    #'Thrust Right':'*+g',
    #'Thrust Left':'*+h',
    'Boost':'*+i',
    'Primary Fire':'*+j',
    'Secondary Fire':'*+k',
    'Next Fire Group':'*+l',
    'Previous Fire Group':'*+m'}
    
    
    # Configure preset flight patterns
    pattern_specs_for_hotkeys = {
    keys_for_actions['Pitch Up']: ('Wave Down Inc', None, 1000),
    keys_for_actions['Thrust Up']: ('Wave Down Inc', None, 1000),
    keys_for_actions['Pitch Down']: ('Wave Up Inc', None, 1000),
    keys_for_actions['Thrust Down']: ('Wave Up Inc', None, 1000),
    keys_for_actions['Roll Right']: ('Wave Left Inc', None, 1000),
    keys_for_actions['Thrust Right']: ('Wave Left Inc', None, 1000),
    keys_for_actions['Roll Left']: ('Wave Right Inc', None, 1000),
    keys_for_actions['Thrust Left']: ('Wave Right Inc', None, 1000),
    keys_for_actions['Boost']: ('Boost', None, None)
    }
    
    # Load available patterns
    patterns_path = 'patterns/'
    pattern_names = [f[:-5] for f in listdir(patterns_path) if isfile(join(patterns_path, f))]
    for pattern_name in pattern_names:
        print('Registering pattern: ', pattern_name)
        player.register(pattern_name, f'{patterns_path}{pattern_name}.tact')
    
    # Register hotkey listeners for flight patterns
    for hotkey in pattern_specs_for_hotkeys:
        pattern_name, charge_millis, repeat_millis = pattern_specs_for_hotkeys[hotkey]
        if pattern_name not in pattern_names:
            raise Exception(f'Pattern {pattern_name} not found in local {patterns_path} directory!')
        print(f'Adding hotkey pattern spec: {hotkey} -> {pattern_name} after {charge_millis}ms for {repeat_millis}ms')
        keyboard.add_hotkey(hotkey, lambda n=pattern_name, h=hotkey, c=charge_millis, r=repeat_millis : play(n, h, c, r))
    
    # Configure set weapon patterns
    pattern_specs_for_weapons = {'N/A': (None, None, None),
    'Huge Multi': ('Short Fade Out 30ms Delay VestArms', None, 300),
    'Large Multi': ('Continuous Vest20Arms10', None, 500),
    'Medium Multi': ('Arms Continuous 10', None, 500),
    'Huge Cannon': ('Reverberating Short Fade Out 30ms Delay VestArms', None, None),
    'Large Cannon': ('Short Fade Out 30ms Delay VestArms', None, None),
    'Medium Cannon': ('Short Fade Out 30ms Delay Arms', None, None),
    'Huge PA': ('Reverberating Short Fade Out 30ms Delay VestArms', None, None),
    'Large PA': ('Short Fade Out 30ms Delay VestArms', None, None),
    'Medium PA': ('Short Fade Out 30ms Delay Arms', None, None),
    'Medium Rails': ('Reverberating Short Fade Out 30ms Delay VestArms', 600, None),
    'Small Rails': ('Short Fade Out 30ms Delay Arms', 400, None),
    'Imperial Hammer': ('Reverberating Burst3 20ms Delay VestArms', 600, None)} # Add Arms

    # Configure loadout and assign primary and secondary fire to related patterns for each fire group.
    print('Supported Weapons (Select one size up if your ship does not support the largest option of your weapon.):')
    for weapon in pattern_specs_for_weapons:
        print('\t' + weapon)
    
    # Configure num fire groups
    while num_fire_groups < 1:
        err = False
        try:
            num_fire_groups = int(input('Set number of fire groups: '))
            err = (num_fire_groups < 1)
        except ValueError as ve:
            err = True
        if err:
            print('Must enter an integer greater than 0!')
    
    for fire_group_idx in range(num_fire_groups):
        # Primary Fire
        primary_weapon = None
        while primary_weapon not in pattern_specs_for_weapons:
            primary_weapon = input(f'Choose primary weapon for Fire Group {fire_group_idx+1}/{num_fire_groups}: ')
        primary_fire_pattern_specs.append(pattern_specs_for_weapons[primary_weapon])
        if primary_weapon != 'N/A':
            hotkey = keys_for_actions['Primary Fire']
            pattern_name, charge_millis, repeat_millis = pattern_specs_for_weapons[primary_weapon]
            if pattern_name not in pattern_names:
                raise Exception(f'Pattern {pattern_name} not found in local {patterns_path} directory!')
            print(f'Adding hotkey pattern spec: {hotkey} -> {pattern_name} after {charge_millis}ms for {repeat_millis}ms while in Fire Group {fire_group_idx+1}/{num_fire_groups}')
            keyboard.add_hotkey(hotkey, lambda h=hotkey : play_primary_fire(h))
            
        
        # Secondary Fire
        secondary_weapon = None
        while secondary_weapon not in pattern_specs_for_weapons:
            secondary_weapon = input(f'Choose secondary weapon for Fire Group {fire_group_idx+1}/{num_fire_groups}: ')
        secondary_fire_pattern_specs.append(pattern_specs_for_weapons[secondary_weapon])
        if secondary_weapon != 'N/A':
            hotkey = keys_for_actions['Secondary Fire']
            pattern_name, charge_millis, repeat_millis = pattern_specs_for_weapons[secondary_weapon]
            if pattern_name not in pattern_names:
                raise Exception(f'Pattern {pattern_name} not found in local {patterns_path} directory!')
            print(f'Adding hotkey pattern spec: {hotkey} -> {pattern_name} after {charge_millis}ms for {repeat_millis}ms while in Fire Group {fire_group_idx+1}/{num_fire_groups}')
            keyboard.add_hotkey(hotkey, lambda h=hotkey : play_secondary_fire(h))
        
        #print('D) ', primary_fire_pattern_specs) #debug
        #print(f'D) current_fire_group_idx: {current_fire_group_idx}') #debug
        
    # Configure fire group control hotkeys
    keyboard.add_hotkey(keys_for_actions['Next Fire Group'], lambda : update_fire_group(1))
    keyboard.add_hotkey(keys_for_actions['Previous Fire Group'], lambda : update_fire_group(-1))
    
    run()