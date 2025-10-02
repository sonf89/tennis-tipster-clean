# shim.py — importa dal modulo “core” a prescindere dal nome file usato
try:
    from app_utils import *
except ModuleNotFoundError:
    from utils import *
