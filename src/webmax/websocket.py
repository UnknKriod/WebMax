import os
import json
import asyncio
from typing import Dict

import websockets

from .errors import NeedRestartError
from .rate_limiter import RateLimiter
from .static import MessageStatus, Opcode, ChatActions
from .entities import Message, ChatAction
from .exceptions import ApiError

class WebsocketMixin:
	rate_limiters: Dict[int, RateLimiter]
	default_rate_limiter: RateLimiter

	async def connect_web_socket(self):
		try:
			self.websocket = await websockets.connect(self.uri, additional_headers=self.headers)
		except Exception as e:
			raise ConnectionError(f'Ошибка подключения. {e}')

	async def message_receiver(self):
		"""
		Получатель сообщений из WebSocket.
		Оптимизирован для минимизации CPU нагрузки.
		"""
		while True:
			try:
				raw_response = await self.websocket.recv()
				response = json.loads(raw_response)
				seq = response.get('seq')

				if seq is not None and seq in self._response_waiters:
					future = self._response_waiters.pop(seq)
					if not future.done():
						future.set_result(response)
				else:
					await self._recv_queue.put(response)
			except websockets.ConnectionClosedError:
				# Соединение закрыто. Добавляем небольшую задержку перед повторным попыткам.
				await asyncio.sleep(0.1)
			except asyncio.CancelledError:
				# Корректное завершение задачи
				break
			except Exception as e:
				# Логируем ошибку и добавляем задержку для предотвращения busy-loop
				print(f"⚠️ Ошибка в message_receiver: {e}")
				await asyncio.sleep(0.1)

	async def action_handler(self):
		"""
		Обработчик действий из очереди.
		Оптимизирован для минимизации CPU нагрузки.
		"""
		while True:
			try:
				# Используем timeout для предотвращения busy-waiting при пустой очереди
				response = await asyncio.wait_for(self._recv_queue.get(), timeout=1.0)
				cmd = response.get('cmd')
				opcode = response.get('opcode')
				payload = response.get('payload', {})

				if opcode == Opcode.NOTIF_MESSAGE:
					await self.notif_message(payload)
				elif opcode == Opcode.NOTIF_CHAT_ACTION:
					await self.notif_chat_action(payload)
			except asyncio.TimeoutError:
				# Очередь пуста — просто продолжаем цикл с минимальной нагрузкой
				continue
			except asyncio.CancelledError:
				# Корректное завершение задачи
				break
			except Exception as e:
				print(f"⚠️ Ошибка в action_handler: {e}")
				await asyncio.sleep(0.01)

	async def notif_message(self, payload: dict):
		raw_data = payload.get('message', {})
		chat_id = payload.get('chatId')
		raw_data['chat_id'] = chat_id
		message = Message.from_raw_data(raw_data=raw_data, chat_id=chat_id, client=self)

		chat = self.chats.get(chat_id)

		if message.sender is None:
			return

		if not (message.sender.id in self.contacts):
			await self.get_contacts_info(contact_ids=[message.sender.id])
		contact = self.contacts.get(message.sender.id)

		if message.status == MessageStatus.REMOVED:
			for handler in self.on_message_removed_handlers:
				if asyncio.iscoroutinefunction(handler):
					await handler(message=message)
				else:
					handler(message=message)
		else:
			for handler in self.on_message_handlers:
				if asyncio.iscoroutinefunction(handler):
					await handler(message=message)
				else:
					handler(message=message)

	async def notif_chat_action(self, payload: dict):
		type = payload.get('type')
		chat_id = payload.get('chatId')
		user_id = payload.get('userId')

		chat = self.chats.get(chat_id)

		if not (user_id in self.contacts):
			await self.get_contacts_info(contact_ids=[user_id])
		user = self.contacts.get(user_id)

		action = ChatAction(
			type=type or ChatActions.TYPING,
			chat=chat,
			user=user
		)

		for action_filter, handler in self.on_chat_action_handlers:
			if action_filter is None or action_filter == 'typing':
				if asyncio.iscoroutinefunction(handler):
					await handler(action)
				else:
					handler(action)

	async def ping_loop(self):
		consecutive_failures = 0
		while True:
			try:
				await self.ping()
				consecutive_failures = 0
				await asyncio.sleep(60)
			except asyncio.CancelledError:
				break
			except Exception as e:
				print(f"⚠️ Ошибка в ping_loop: {e}")
				consecutive_failures += 1
				if consecutive_failures >= 10:
					print("❌ Критическое количество ошибок ping_loop. Перезапускаем клиент...")
					raise NeedRestartError("WebSocket connection lost")
				await asyncio.sleep(5)

	async def do_api_request(self, opcode: int, payload: dict, retry: bool = True):
		"""
		Отправить API-запрос через WebSocket.
		При разрыве соединения автоматически переподключается и повторяет запрос (один раз).
		"""
		if self.websocket is None:
			raise ConnectionError('Вебсокет не подключен')

		limiter = self.rate_limiters.get(opcode, self.default_rate_limiter)
		await limiter.acquire()

		message = {
			'ver': self.ver,
			'cmd': 0,
			'seq': self.seq,
			'opcode': opcode,
			'payload': payload
		}

		future = asyncio.Future()
		self._response_waiters[self.seq] = future

		try:
			await self.websocket.send(json.dumps(message))
		except (websockets.exceptions.ConnectionClosedError, ConnectionError) as e:
			raise ConnectionError(f"WebSocket connection lost: {e}") from e

		expected_seq = self.seq
		self.seq += 1

		try:
			response = await future
			cmd = response.get('cmd')
			if cmd == 1 and response.get('seq') == expected_seq:
				return response
			elif cmd == 3:
				error_message = response.get('payload', {}).get('localizedMessage', 'Неизвестная ошибка')
				error_type = response.get('payload', {}).get('error', 'Неизвестный тип ошибки')
				if error_type == 'login.token':
					os.remove(f'{self.session_name}.db')
				raise ApiError(f'{error_message} ({error_type})')
		except asyncio.CancelledError:
			if expected_seq in self._response_waiters:
				del self._response_waiters[expected_seq]
			raise
		except Exception as e:
			# Любая другая ошибка (таймаут и т.п.)
			if expected_seq in self._response_waiters:
				del self._response_waiters[expected_seq]
			raise