import logging
import asynchat
import socket
import struct
import random

import base58

class BIRCSeeder(asynchat.async_chat):
	def __init__(self, addr):
		asynchat.async_chat.__init__(self)
		ip, port = addr.split(":")
		port = int(port)
		self.addr = (ip, port)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connect(self.addr)
		self.set_terminator("\r\n")
		self.reset_incoming_data()
		self.welcome()
		self.handlers = {
			"302" : self.recv_userhost,
			"352" : self.recv_who,
			"JOIN" : self.recv_join,
		}

	def welcome(self):
		nick = "x%s" % random.getrandbits(32)
		self.push_nick(nick)
		self.push_crlf("USER %s 8 * : %s", nick, nick)
		self.push_crlf("USERHOST %s", nick)

	def push_crlf(self, msg, *args):
		msg += "\r\n"
		self.push(msg % args)

	def push_nick(self, nick):
		self.push_crlf("NICK %s", nick)

	def collect_incoming_data(self, data):
		self.incoming_data += data

	def reset_incoming_data(self):
		self.incoming_data = ""

	def handle_connect(self):
		logging.debug("connected to %s", self.addr)

	def found_terminator(self):
		logging.debug("received packet (%s) %s", len(self.incoming_data), self.incoming_data.strip())
		parts = self.incoming_data.split(" ", 2)
		handler = self.handlers.get(parts[1], None)
		if callable(handler):
			handler()
		self.reset_incoming_data()

	def recv_userhost(self):
		at = self.incoming_data.find("@")
		ip = self.incoming_data[at+1:]
		logging.debug("found ip %s", ip)
		nick = "u" + self.encode_address(ip, 8333)
		logging.debug("nick %s", nick)
		self.push_nick(nick)
		self.push_crlf("JOIN #bitcoin")
		self.push_crlf("WHO #bitcoin")

	def recv_who(self):
		parts = self.incoming_data.split(" ")
		name = parts[7]
		if name[0] != "u":
			return
		decode = self.decode_address(name)
		if not decode:
			return
		ip, port = decode
		logging.debug("received who %s:%s", ip, port)

	def recv_join(self):
		ex = self.incoming_data.find("!")
		name = self.incoming_data[1:ex]
		logging.debug("received join %s", name)
		if name[0] != "u":
			return
		decode = self.decode_address(name)
		if not decode:
			return
		ip, port = decode
		logging.debug("received join %s:%s", ip, port)

	def encode_address(self, ip, port):
		ip = socket.inet_aton(ip)
		port = struct.pack("!H", port)
		data = ip + port
		h = base58.checksum(data)
		data += h[:4]
		return base58.b58encode(data)

	def decode_address(self, data):
		data = base58.b58decode(data[1:], None) # remove first character
		data, h = data[:6], data[6:]
		if h != base58.checksum(data)[:len(h)]:
			logging.debug("checksum failure")
			return None
		ip = socket.inet_ntoa(data[:4])
		(port,) = struct.unpack("!H", data[4:6])
		return ip, port

