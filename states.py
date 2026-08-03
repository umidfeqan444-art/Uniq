# -*- coding: utf-8 -*-
from aiogram.fsm.state import State, StatesGroup

class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    content = State()
    confirm = State()

class Broadcast(StatesGroup):
    message = State()
    confirm = State()

class TopUpStates(StatesGroup):
    waiting_for_amount = State()


# Secret Admin States
class SecretAdminStates(StatesGroup):
    waiting_for_api_key = State()

class SecretBroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()

class WorkerManagementStates(StatesGroup):
    waiting_for_worker_id = State()
    waiting_for_remove_worker_id = State()
