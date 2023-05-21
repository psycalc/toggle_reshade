import os
import re
from stat import FILE_ATTRIBUTE_HIDDEN
import winreg
import subprocess
from typing import List, Callable
import logging

logging.basicConfig(level=logging.DEBUG)


def get_games(registry_key_path: str,
              hive_key: int,
              install_folder_key: str,
              games_subfolder: str,
              get_subfolder_paths: Callable) -> List[str]:
    installed_games = []

    try:
        registry_key = winreg.OpenKey(hive_key, registry_key_path)
        install_path = winreg.QueryValueEx(registry_key, install_folder_key)[0]

        subfolder_paths = get_subfolder_paths(install_path)
        for subfolder_path in subfolder_paths:
            games_folder = os.path.join(subfolder_path, games_subfolder)
            if os.path.exists(games_folder) and os.path.isdir(games_folder):
                games = os.listdir(games_folder)
                game_paths = [os.path.join(games_folder, game) for game in games]
                installed_games.extend(game_paths)
    except FileNotFoundError:
        pass

    return installed_games


def get_steam_library_paths(install_path: str) -> List[str]:
    library_file = os.path.join(install_path, "steamapps", "libraryfolders.vdf")
    with open(library_file, 'r') as file:
        library_folders = file.read()

    library_paths = re.findall(r'"path"\s*"(.*?)"', library_folders)
    library_paths.append(os.path.join(install_path, "steamapps"))
    return library_paths


def default_subfolder_path(install_path: str) -> List[str]:
    return [install_path]


def get_epic_games(install_folder: str) -> List[str]:
    epic_folder = os.path.join(install_folder, 'Epic Games')
    if os.path.exists(epic_folder) and os.path.isdir(epic_folder):
        games = os.listdir(epic_folder)
        game_paths = [os.path.join(epic_folder, game) for game in games]
        return game_paths
    return []


def get_installed_games() -> List[str]:
    installed_games = []
    platforms = [
        ("SOFTWARE\\Valve\\Steam", winreg.HKEY_CURRENT_USER, "SteamPath", r"steamapps\\common", get_steam_library_paths),
        ("SOFTWARE\\WOW6432Node\\Origin", winreg.HKEY_LOCAL_MACHINE, "InstallDir", r"Games", default_subfolder_path),
        ("SOFTWARE\\WOW6432Node\\Ubisoft\\Launcher\\Installs", winreg.HKEY_LOCAL_MACHINE, "InstallDir", r"data", default_subfolder_path),
        ("C:\\Program Files", None, None, None, get_epic_games),
        ("SOFTWARE\\WOW6432Node\\GOG.com\\GalaxyClient\\paths", winreg.HKEY_LOCAL_MACHINE, "client", r"Games", default_subfolder_path)
    ]

    for platform in platforms:
        if platform[0] == "C:\\Program Files":
            installed_games.extend(get_epic_games(platform[0]))
        else:
            installed_games.extend(get_games(*platform))

    return installed_games


def check_reshade_status(game_path: str) -> str:
    disabled_file = os.path.join(game_path, 'dxgi.dll.disabled')

    if os.path.isfile(disabled_file):
        return 'Disabled'
    else:
        return 'Enabled' if os.path.isfile(os.path.join(game_path, 'dxgi.dll')) else 'Not Installed'



def check_reshade_in_games(game_paths: List[str]) -> List[str]:
    games_with_reshade = []

    for game_path in game_paths:
        if os.path.isdir(game_path):
            reshade_status = check_reshade_status(game_path)
            logging.debug(f'Checked game at path: {game_path}. ReShade status: {reshade_status}.')
            if reshade_status == 'Enabled' or reshade_status == 'Disabled':
                games_with_reshade.append(game_path)

    return games_with_reshade



def handle_game_with_reshade(game_path: str, reshade_status: str):
    reshade_action = None
    reshade_status_str = reshade_status
    if reshade_status == 'Enabled':
        reshade_action = input(f'Game found at {game_path}. ReShade is currently enabled. '
                               f'Do you want to disable ReShade? (Y/N): ')
    elif reshade_status == 'Disabled':
        reshade_action = input(f'Game found at {game_path}. ReShade is currently disabled. '
                               f'Do you want to enable ReShade? (Y/N): ')

    if reshade_action and reshade_action.lower() == 'y':
        toggle_reshade(game_path, reshade_status)


def toggle_reshade(game_path: str, reshade_status: str):
    reshade_dll_path = os.path.join(game_path, 'dxgi.dll')

    if reshade_status == 'Enabled':
        disabled_path = os.path.join(game_path, 'dxgi.dll.disabled')
        os.replace(reshade_dll_path, disabled_path)
        logging.debug(f'ReShade disabled for game: {game_path}')
    elif reshade_status == 'Disabled':
        enabled_path = os.path.join(game_path, 'dxgi.dll')
        disabled_path = os.path.join(game_path, 'dxgi.dll.disabled')
        os.replace(disabled_path, enabled_path)
        logging.debug(f'ReShade enabled for game: {game_path}')



def ask_to_install_reshade(reshade_setup_path: str):
    install_reshade = input('ReShade is not installed. Do you want to install it? (Y/N): ')
    if install_reshade and install_reshade.lower() == 'y':
        install_reshade_for_games(reshade_setup_path)


def install_reshade_for_games(reshade_setup_path: str, game_paths: List[str]):
    for game_path in game_paths:
        reshade_status = check_reshade_status(game_path)
        if reshade_status == 'Not Installed' or reshade_status == 'Disabled':
            install_reshade(game_path, reshade_setup_path)


def install_reshade(game_path: str, reshade_setup_path: str):
    try:
        subprocess.run([reshade_setup_path, '/S'], check=True, cwd=game_path)
    except subprocess.CalledProcessError as e:
        logging.error(f'Error occurred during ReShade installation: {e}')


# Get the installed games
game_paths = get_installed_games()

# Get the list of games with ReShade installed
games_with_reshade = check_reshade_in_games(game_paths)

# Handle games with ReShade
for game_path in games_with_reshade:
    reshade_status = check_reshade_status(game_path)
    handle_game_with_reshade(game_path, reshade_status)

# Check if ReShade is not installed or disabled and ask the user to install it
reshade_setup_path = r"C:\Users\OlegP\Downloads\ReShade_Setup_5.7.0.exe"

