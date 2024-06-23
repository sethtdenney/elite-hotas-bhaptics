from time import sleep
from bhaptics import better_haptic_player as player
import keyboard
from pynput import keyboard as pynputkeyboard
import os
from os import listdir
from os.path import isfile, join
from tail import Tail
import re
from threading import Thread

# Set to True to print debug logs and False otherwise
debug = False

hotkey_listeners = []
num_fire_groups = 0
current_fire_group_idx = 0
primary_fire_pattern_specs = []
secondary_fire_pattern_specs = []

def get_current_graduated_intensity(num_repeats, num_repeats_to_increase_intensity):
    tier = int(num_repeats / num_repeats_to_increase_intensity) + 1
    if keyboard.is_pressed('9'):
        max_tier = 10
    elif keyboard.is_pressed('8'):
        max_tier = 9
    elif keyboard.is_pressed('7'):
        max_tier = 8
    elif keyboard.is_pressed('6'):
        max_tier = 7
    elif keyboard.is_pressed('5'):
        max_tier = 6
    elif keyboard.is_pressed('4'):
        max_tier = 5
    elif keyboard.is_pressed('3'):
        max_tier = 4
    elif keyboard.is_pressed('2'):
        max_tier = 3
    elif keyboard.is_pressed('1'):
        max_tier = 2
    else:
        max_tier = 1
    return 0.1 * min(tier, max_tier)

def play(pattern_name, hotkey=None, charge_duration_millis=None, repeat_intervial_millis=None, num_repeats_to_increase_intensity=None):
    print(f'Preparing {pattern_name} in response to hotkey {hotkey}')
    
    # If a charge time is configured, only proceed if the hotkey is held for the full charge duration.
    if charge_duration_millis:
        charged = False
        for t in range(int(charge_duration_millis / 50)):
            sleep(0.05)
            if not keyboard.is_pressed(hotkey):
                if debug: print(f'Did not pass charge check for hotkey \'{hotkey}\'. Aborting...')
                return
    
    # If repeat is configured, repeat pattern as long as the hotkey is held.
    if not repeat_intervial_millis:
        print('Executing', pattern_name)
        player.submit_registered(pattern_name)
    else:
        print('Executing with repeat', pattern_name)
        if debug: print(f'Entering hold loop while hotkey \'{hotkey}\' is held down...')
        num_repeats = 0
        while keyboard.is_pressed(hotkey):
            if debug: print(f'Repeating pattern for hotkey \'{hotkey}\'')
            if num_repeats_to_increase_intensity is None:
                intensity = 1
            else: intensity = get_current_graduated_intensity(num_repeats, num_repeats_to_increase_intensity)
            player.submit_registered_with_option(pattern_name, "alt", # No clue what this parameter 'altKey' actually does...
                                             scale_option={"intensity": intensity, "duration": 1},
                                             rotation_option={"offsetAngleX": 0, "offsetY": 0})
            if debug: print(f'Playing with intensity of {intensity}')
            sleep(repeat_intervial_millis / 1000.0)
            num_repeats += 1
    if debug: print(f'Finished playing pattern for hotkey \'{hotkey}\'')

def play_primary_fire(hotkey):
    pattern_name, charge_millis, repeat_millis, repeats_to_graduate = primary_fire_pattern_specs[current_fire_group_idx]
    play(pattern_name, hotkey, charge_millis, repeat_millis, repeats_to_graduate)

def play_secondary_fire(hotkey):
    pattern_name, charge_millis, repeat_millis, repeats_to_graduate = secondary_fire_pattern_specs[current_fire_group_idx]
    play(pattern_name, hotkey, charge_millis, repeat_millis, repeats_to_graduate)

def update_fire_group(delta):
    global current_fire_group_idx
    current_fire_group_idx = (current_fire_group_idx + delta) % num_fire_groups
    print(f'New Fire Group {current_fire_group_idx+1}/{num_fire_groups}')

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

def add_new_hotkey_listener(hotkey, callback):
    if debug: print(f'Adding new hotkey listener for hotkey \'{hotkey}\'')
    global hotkey_listeners
    hotkey_state = pynputkeyboard.HotKey(
        pynputkeyboard.HotKey.parse(hotkey),
        callback)
    listener = pynputkeyboard.Listener(
        on_press=hotkey_state.press,
        on_release=hotkey_state.release)
    hotkey_listeners.append(listener)

def run():
    # Run log listener daemon
    run_log_listener_daemon()
    
    # Run hotkey listeners
    if debug: print(f'Starting {len(hotkey_listeners)} hotkey listeners.')
    for listener in hotkey_listeners:
        listener.start()
    
    print("Press ctrl+z+enter to quit")
    keyboard.wait('ctrl+z+enter')
    print("Stopping listeners...")
    
    # Stop hotkey listeners
    for listener in hotkey_listeners:
        listener.stop()
    
    os._exit(0)

if __name__ == "__main__":
    player.initialize()
    
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
    keys_for_actions['Pitch Up']: ('Wave Down Inc', None, 1000, 2),
    #keys_for_actions['Thrust Up']: ('Wave Down Inc', None, 1000, 2),
    keys_for_actions['Pitch Down']: ('Wave Up Inc', None, 1000, 2),
    #keys_for_actions['Thrust Down']: ('Wave Up Inc', None, 1000, 2),
    keys_for_actions['Roll Right']: ('Wave Left Inc', None, 1000, 2),
    #keys_for_actions['Thrust Right']: ('Wave Left Inc', None, 1000, 2),
    keys_for_actions['Roll Left']: ('Wave Right Inc', None, 1000, 2),
    #keys_for_actions['Thrust Left']: ('Wave Right Inc', None, 1000, 2),
    keys_for_actions['Boost']: ('Boost', None, None, None)
    }
    
    # Load available patterns
    patterns_path = 'patterns/'
    pattern_names = [f[:-5] for f in listdir(patterns_path) if isfile(join(patterns_path, f))]
    for pattern_name in pattern_names:
        print('Registering pattern: ', pattern_name)
        player.register(pattern_name, f'{patterns_path}{pattern_name}.tact')
    
    # Register hotkey listeners for flight patterns
    for hotkey in pattern_specs_for_hotkeys:
        pattern_name, charge_millis, repeat_millis, repeats_to_graduate = pattern_specs_for_hotkeys[hotkey]
        if pattern_name not in pattern_names:
            raise Exception(f'Pattern {pattern_name} not found in local {patterns_path} directory!')
        print(f'Adding hotkey pattern spec: {hotkey} -> {pattern_name} after {charge_millis}ms every {repeat_millis}ms')
        add_new_hotkey_listener(hotkey, lambda n=pattern_name, h=hotkey, c=charge_millis, r=repeat_millis, g=repeats_to_graduate : play(n, h, c, r, g))
    
    # Configure set weapon patterns
    pattern_specs_for_weapons = {'N/A': (None, None, None, None),
    'Huge Multi': ('Short Fade Out 30ms Delay VestArms', None, 300, None),
    'Large Multi': ('Continuous Vest20Arms10', None, 500, None),
    'Medium Multi': ('Arms Continuous 10', None, 500, None),
    'Huge Cannon': ('Reverberating Short Fade Out 30ms Delay VestArms', None, None, None),
    'Large Cannon': ('Short Fade Out 30ms Delay VestArms', None, None, None),
    'Medium Cannon': ('Short Fade Out 30ms Delay Arms', None, None, None),
    'Huge PA': ('Reverberating Short Fade Out 30ms Delay VestArms', None, None, None),
    'Large PA': ('Short Fade Out 30ms Delay VestArms', None, None, None),
    'Medium PA': ('Short Fade Out 30ms Delay Arms', None, None, None),
    'Medium Rails': ('Reverberating Short Fade Out 30ms Delay VestArms', 600, None, None),
    'Small Rails': ('Short Fade Out 30ms Delay Arms', 400, None, None),
    'Imperial Hammer': ('Reverberating Burst3 20ms Delay VestArms', 600, None, None)}
    
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
    
    # Configure loadout and assign primary and secondary fire to related patterns for each fire group.
    print('Supported Weapons (Select one size up if your ship does not support the largest option of your weapon.):')
    weapon_order = []
    idx = 0
    for weapon in pattern_specs_for_weapons:
        weapon_order.append(weapon)
        print(f'\t{idx}) {weapon}')
        idx += 1
    
    for fire_group_idx in range(num_fire_groups):
        # Primary Fire
        primary_weapon = None
        while primary_weapon not in pattern_specs_for_weapons:
            try:
                primary_weapon_idx = int(input(f'Choose primary weapon (number) for Fire Group {fire_group_idx+1}/{num_fire_groups}: '))
                err = (primary_weapon_idx < 0 or primary_weapon_idx >= len(weapon_order))
            except ValueError as ve:
                err = True
            if err:
                print('Must enter an integer corresponding to a supported weapon (see above list)!')
            else:
                primary_weapon = weapon_order[primary_weapon_idx]
        primary_fire_pattern_specs.append(pattern_specs_for_weapons[primary_weapon])
        if primary_weapon != 'N/A':
            hotkey = keys_for_actions['Primary Fire']
            pattern_name, charge_millis, repeat_millis, repeats_to_graduate = pattern_specs_for_weapons[primary_weapon]
            if pattern_name not in pattern_names:
                raise Exception(f'Pattern {pattern_name} not found in local {patterns_path} directory!')
            print(f'Adding hotkey pattern spec: {hotkey} -> {pattern_name} after {charge_millis}ms every {repeat_millis}ms while in Fire Group {fire_group_idx+1}/{num_fire_groups}')
        
        # Secondary Fire
        secondary_weapon = None
        while secondary_weapon not in pattern_specs_for_weapons:
            try:
                secondary_weapon_idx = int(input(f'Choose secondary weapon (number) for Fire Group {fire_group_idx+1}/{num_fire_groups}: '))
                err = (secondary_weapon_idx < 0 or secondary_weapon_idx >= len(weapon_order))
            except ValueError as ve:
                err = True
            if err:
                print('Must enter an integer corresponding to a supported weapon (see above list)!')
            else:
                secondary_weapon = weapon_order[secondary_weapon_idx]
        secondary_fire_pattern_specs.append(pattern_specs_for_weapons[secondary_weapon])
        if secondary_weapon != 'N/A':
            hotkey = keys_for_actions['Secondary Fire']
            pattern_name, charge_millis, repeat_millis, repeats_to_graduate = pattern_specs_for_weapons[secondary_weapon]
            if pattern_name not in pattern_names:
                raise Exception(f'Pattern {pattern_name} not found in local {patterns_path} directory!')
            print(f'Adding hotkey pattern spec: {hotkey} -> {pattern_name} after {charge_millis}ms every {repeat_millis}ms while in Fire Group {fire_group_idx+1}/{num_fire_groups}')
    
    # Configure only one listener for each of primary and secondary fire, regardless of the number of fire groups.
    add_new_hotkey_listener(keys_for_actions['Primary Fire'], lambda h=keys_for_actions['Primary Fire'] : play_primary_fire(h))
    add_new_hotkey_listener(keys_for_actions['Secondary Fire'], lambda h=keys_for_actions['Secondary Fire'] : play_secondary_fire(h))
    
    # Configure fire group control hotkeys
    add_new_hotkey_listener(keys_for_actions['Next Fire Group'], lambda : update_fire_group(1))
    add_new_hotkey_listener(keys_for_actions['Previous Fire Group'], lambda : update_fire_group(-1))
    
    run()