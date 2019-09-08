#!/usr/bin/env python

from __future__ import print_function

"""Bluetooth Low Energy Python interface"""
import sys
import datetime
import os
import time
import subprocess
import binascii
import select
import struct
import signal
import math
import sys
from collections import namedtuple
from struct import *

def preexec_function():
	# Ignore the SIGINT signal by setting the handler to the standard
	# signal handler SIG_IGN.
	signal.signal(signal.SIGINT, signal.SIG_IGN)

Debugging = False
script_path = os.path.join(os.path.abspath(os.path.dirname(__file__)))
helperExe = os.path.join(script_path, "bluepy-helper")

SEC_LEVEL_LOW = "low"
SEC_LEVEL_MEDIUM = "medium"
SEC_LEVEL_HIGH = "high"

ADDR_TYPE_PUBLIC = "public"
ADDR_TYPE_RANDOM = "random"

def DBG(*args):
	if Debugging:
		msg = " ".join([str(a) for a in args])
		print(msg)


class BTLEException(Exception):
	"""Base class for all Bluepy exceptions"""
	def __init__(self, message, resp_dict=None):
		self.message = message

		# optional messages from bluepy-helper
		self.estat = None
		self.emsg = None
		if resp_dict:
			self.estat = resp_dict.get('estat',None)
			if isinstance(self.estat,list):
				self.estat = self.estat[0]
			self.emsg = resp_dict.get('emsg',None)
			if isinstance(self.emsg,list):
				self.emsg = self.emsg[0]


	def __str__(self):
		msg = self.message
		if self.estat or self.emsg:
			msg = msg + " ("
			if self.estat:
				msg = msg + "code: %s" % self.estat
			if self.estat and self.emsg:
				msg = msg + ", "
			if self.emsg:
				msg = msg + "error: %s" % self.emsg
			msg = msg + ")"

		return msg

class BTLEInternalError(BTLEException):
	def __init__(self, message, rsp=None):
		BTLEException.__init__(self, message, rsp)

class BTLEDisconnectError(BTLEException):
	def __init__(self, message, rsp=None):
		BTLEException.__init__(self, message, rsp)

class BTLEManagementError(BTLEException):
	def __init__(self, message, rsp=None):
		BTLEException.__init__(self, message, rsp)

class BTLEGattError(BTLEException):
	def __init__(self, message, rsp=None):
		BTLEException.__init__(self, message, rsp)



class UUID:
	def __init__(self, val, commonName=None):
		'''We accept: 32-digit hex strings, with and without '-' characters,
		   4 to 8 digit hex strings, and integers'''
		if isinstance(val, int):
			if (val < 0) or (val > 0xFFFFFFFF):
				raise ValueError(
					"Short form UUIDs must be in range 0..0xFFFFFFFF")
			val = "%04X" % val
		elif isinstance(val, self.__class__):
			val = str(val)
		else:
			val = str(val)  # Do our best

		val = val.replace("-", "")
		if len(val) <= 8:  # Short form
			val = ("0" * (8 - len(val))) + val + "00001000800000805F9B34FB"

		self.binVal = binascii.a2b_hex(val.encode('utf-8'))
		if len(self.binVal) != 16:
			raise ValueError(
				"UUID must be 16 bytes, got '%s' (len=%d)" % (val,
															  len(self.binVal)))
		self.commonName = commonName

	def __str__(self):
		s = binascii.b2a_hex(self.binVal).decode('utf-8')
		return "-".join([s[0:8], s[8:12], s[12:16], s[16:20], s[20:32]])

	def __eq__(self, other):
		return self.binVal == UUID(other).binVal

	def __cmp__(self, other):
		return cmp(self.binVal, UUID(other).binVal)

	def __hash__(self):
		return hash(self.binVal)

	def getCommonName(self):
		s = AssignedNumbers.getCommonName(self)
		if s:
			return s
		s = str(self)
		if s.endswith("-0000-1000-8000-00805f9b34fb"):
			s = s[0:8]
			if s.startswith("0000"):
				s = s[4:]
		return s

class Service:
	def __init__(self, *args):
		(self.peripheral, uuidVal, self.hndStart, self.hndEnd) = args
		self.uuid = UUID(uuidVal)
		self.chars = None
		self.descs = None

	def getCharacteristics(self, forUUID=None):
		if not self.chars: # Unset, or empty
			self.chars = [] if self.hndEnd <= self.hndStart else self.peripheral.getCharacteristics(self.hndStart, self.hndEnd)
		if forUUID is not None:
			u = UUID(forUUID)
			return [ch for ch in self.chars if ch.uuid==u]
		return self.chars

	def getDescriptors(self, forUUID=None):
		if not self.descs:
			# Grab all descriptors in our range, except for the service
			# declaration descriptor
			all_descs = self.peripheral.getDescriptors(self.hndStart+1, self.hndEnd)
			# Filter out the descriptors for the characteristic properties
			# Note that this does not filter out characteristic value descriptors
			self.descs = [desc for desc in all_descs if desc.uuid != 0x2803]
		if forUUID is not None:
			u = UUID(forUUID)
			return [desc for desc in self.descs if desc.uuid == u]
		return self.descs

	def __str__(self):
		return "Service <uuid=%s handleStart=%s handleEnd=%s>" % (self.uuid.getCommonName(),
																 self.hndStart,
																 self.hndEnd)

class Characteristic:
	# Currently only READ is used in supportsRead function,
	# the rest is included to facilitate supportsXXXX functions if required
	props = {"BROADCAST":	0b00000001,
			 "READ":		 0b00000010,
			 "WRITE_NO_RESP":0b00000100,
			 "WRITE":		0b00001000,
			 "NOTIFY":	   0b00010000,
			 "INDICATE":	 0b00100000,
			 "WRITE_SIGNED": 0b01000000,
			 "EXTENDED":	 0b10000000,
	}

	propNames = {0b00000001 : "BROADCAST",
				 0b00000010 : "READ",
				 0b00000100 : "WRITE NO RESPONSE",
				 0b00001000 : "WRITE",
				 0b00010000 : "NOTIFY",
				 0b00100000 : "INDICATE",
				 0b01000000 : "WRITE SIGNED",
				 0b10000000 : "EXTENDED PROPERTIES",
	}

	def __init__(self, *args):
		(self.peripheral, uuidVal, self.handle, self.properties, self.valHandle) = args
		self.uuid = UUID(uuidVal)
		self.descs = None

	def read(self):
		return self.peripheral.readCharacteristic(self.valHandle)

	def write(self, val, withResponse=False):
		return self.peripheral.writeCharacteristic(self.valHandle, val, withResponse)

	def getDescriptors(self, forUUID=None, hndEnd=0xFFFF):
		if not self.descs:
			# Descriptors (not counting the value descriptor) begin after
			# the handle for the value descriptor and stop when we reach
			# the handle for the next characteristic or service
			self.descs = []
			for desc in self.peripheral.getDescriptors(self.valHandle+1, hndEnd):
				if desc.uuid in (0x2800, 0x2801, 0x2803):
					# Stop if we reach another characteristic or service
					break
				self.descs.append(desc)
		if forUUID is not None:
			u = UUID(forUUID)
			return [desc for desc in self.descs if desc.uuid == u]
		return self.descs

	def __str__(self):
		return "Characteristic <%s>" % self.uuid.getCommonName()

	def supportsRead(self):
		if (self.properties & Characteristic.props["READ"]):
			return True
		else:
			return False
			
	def supportsNotify(self):
		if (self.properties & Characteristic.props["NOTIFY"]):
			return True
		else:
			return False

	def propertiesToString(self):
		propStr = ""
		for p in Characteristic.propNames:
		   if (p & self.properties):
			   propStr += Characteristic.propNames[p] + " "
		return propStr

	def getHandle(self):
		return self.valHandle

class Descriptor:
	def __init__(self, *args):
		(self.peripheral, uuidVal, self.handle) = args
		self.uuid = UUID(uuidVal)

	def __str__(self):
		return "Descriptor <%s>" % self.uuid.getCommonName()
		

	def read(self):
		return self.peripheral.readCharacteristic(self.handle)

	def write(self, val, withResponse=False):
		self.peripheral.writeCharacteristic(self.handle, val, withResponse)

class DefaultDelegate:
	def __init__(self):
		pass

	def handleNotification(self, cHandle, data):
		DBG("Notification:", cHandle, "sent data", binascii.b2a_hex(data))
		
		#ottenimento ora corrente
		time = datetime.datetime.now()			
		print("\t\tora:",time)
		time_formato_matlab = time.strftime ("%H%M%S.%f")
						
		#occorre capire quale caratteristica è relativa alla notifica ricevuta 
		
		#se l'handle "cHandle" passato a handleNotification è quello corrispondente a temperatura e pressione
		if (cHandle == handle_temp_press):							
			#salvataggio del pacchetto ricevuto in una variabile ausiliaria
			temp_press_value = data
			print("\t\tValore ricevuto temperatura e pressione: ",str(binascii.hexlify(temp_press_value), 'ascii').upper())
			#scomposizione del pacchetto ricevuto in timestamp (2 byte), pressione (4 byte) e temperatura (2 byte)
			timestamp1, pressione, temperatura = unpack('<Hlh', temp_press_value)
			print ("\t\tTimestamp: {}\n\t\tPressione: {} mbar\n\t\tTemperatura: {} °C".format(timestamp1, pressione/100, temperatura/10))
			#scrittura sul file che registra tutti i dati 
			file_valori_sensori.write("Valore ricevuto temperatura e pressione: {}\n\t\tTimestamp: {}\n\t\tPressione: {} mbar\n\t\tTemperatura: {} °C\n".format(str(binascii.hexlify(temp_press_value), 'ascii').upper(), timestamp1, pressione/100, temperatura/10))

		#se l'handle "cHandle" passato a handleNotification è quello corrispondente a accelerometro, giroscopio e magnetometro
		if (cHandle == handle_acc_gyr_magn):
			#salvataggio del pacchetto ricevuto in una variabile ausiliaria
			acc_gyr_magn_value = data
			print("\t\tValore ricevuto accelerometro, giroscopio e magnetometro: ",str(binascii.hexlify(acc_gyr_magn_value), 'ascii').upper())
			#scomposizione del pacchetto ricevuto in timestamp (2 byte), accelerometro, giroscopio e magnetometro 
			#sui tre assi (2 byte con segno per ogni asse)
			timestamp2, acc_x, acc_y, acc_z, gyr_x, gyr_y, gyr_z, magn_x, magn_y, magn_z = unpack('<Hhhhhhhhhh', acc_gyr_magn_value)
			#decodifica dei dati
			#accelerometro (unità di misura: g) con fondo scala +/- 2 g e poichè ricevuti dal bluetooth in mg divido per 1000 per trovare g
			acc_x = acc_x / 1000
			acc_y = acc_y 	/ 1000
			acc_z = acc_z / 1000
			#dati del giroscopio (unità di misura: dps) da dividere per 10 secondo il file "Getting started with the BlueST protocol and SDK.pdf"
			#perchè sono ricevuti in decimi di grado divido per 10 per trovare i gradi
			#fondo scala +/- 2000 dps
			gyr_x = gyr_x / 10
			gyr_y = gyr_y / 10
			gyr_z = gyr_z / 10
			#magnetometro (unità di misura: μT) con range +/- 50 Gauss e fondo scala pari a  ??????,
			#i dati ricevuti sono espressi in milligauss, poichè 1 G = 100 μT, i valori sono infine moltiplicati per 100 ed espressi in μT
			#fondo scala +/- 50 gauss
			magn_x = magn_x / 1000 * 100
			magn_y = magn_y / 1000 * 100
			magn_z = magn_z / 1000 * 100
			print("\t\tTimestamp: {}\n\t\tAccx: {} g\n\t\tAccy: {} g\n\t\tAccz: {} g\n\t\tGyrx: {} dps\n\t\tGyry: {} dps\n\t\tGyrz: {} dps\n\t\tMagnx: {} μT\n\t\tMagny: {} μT\n\t\tMagnz: {} μT\n"
			.format(timestamp2, acc_x, acc_y, acc_z, gyr_x, gyr_y, gyr_z, magn_x, magn_y, magn_z)) 
			#scrittura sul file che registra tutti i dati 
			file_valori_sensori.write("Valore ricevuto accelerometro, giroscopio e magnetometro: {}\n\t\tTimestamp: {}\n\t\tAccx: {} g\n\t\tAccy: {} g\n\t\tAccz: {} g\n\t\tGyrx: {} dps\n\t\tGyry: {} dps\n\t\tGyrz: {} dps\n\t\tMagnx: {} μT\n\t\tMagny: {} μT\n\t\tMagnz: {} μT\n".format(str(binascii.hexlify(acc_gyr_magn_value), 'ascii').upper(), timestamp2, acc_x, acc_y, acc_z, gyr_x, gyr_y, gyr_z, magn_x, magn_y, magn_z))
			#apertura dei file necessari a MATLAB
			file_accelerometro_matlab = open (nome_file_accelerometro_matlab, 'a+')
			file_giroscopio_matlab = open (nome_file_giroscopio_matlab, 'a+')
			file_magnetometro_matlab = open (nome_file_magnetometro_matlab, 'a+')
			#scrittura dei file necessari a MATLAB
			file_accelerometro_matlab.write ("{}\t{}\t{}\t{}\t{}\n".format(timestamp2, time_formato_matlab, acc_x, acc_y, acc_z))
			file_giroscopio_matlab.write ("{}\t{}\t{}\t{}\t{}\n".format(timestamp2, time_formato_matlab, gyr_x, gyr_y, gyr_z))
			file_magnetometro_matlab.write ("{}\t{}\t{}\t{}\t{}\n".format(timestamp2, time_formato_matlab, magn_x, magn_y, magn_z))
			#chiusura dei file necessari a MATLAB
			file_accelerometro_matlab.close()
			file_giroscopio_matlab.close()
			file_magnetometro_matlab.close()

		#se l'handle "cHandle" passato a handleNotification è quello corrispondente al sensor fusion compact
		if (cHandle == handle_sensor_fusion_compact):
			#salvataggio del pacchetto ricevuto in una variabile ausiliaria
			sensor_fusion_compact = data
			print("\t\tValore ricevuto sensor fusion compact: ",str(binascii.hexlify(sensor_fusion_compact), 'ascii').upper())
			file_valori_sensori.write("\t\tValore ricevuto sensor fusion compact: {}".format(str(binascii.hexlify(sensor_fusion_compact), 'ascii').upper()))
			#scomposizione del pacchetto ricevuto in timestamp (2 byte) e altri 9 dati da 2 byte ciascuno secondo il file "Getting started with the BlueST protocol and SDK.pdf"
			timestamp3, qi1, qj1, qk1, qi2, qj2, qk2, qi3, qj3, qk3 = unpack('<Hhhhhhhhhh', sensor_fusion_compact)
			#decodifica dei dati secondo il file "Getting started with the BlueST protocol and SDK.pdf"
			qi1 = qi1 / 10000
			qj1 = qj1 / 10000
			qk1 = qk1 / 10000
			qi2 = qi2 / 10000
			qj2 = qj2 / 10000
			qk2 = qk2 / 10000
			qi3 = qi3 / 10000
			qj3 = qj3 / 10000
			qk3 = qk3 / 10000			
			print("\t\tTimestamp: {}\n\t\tQi1: {} \n\t\tQj1: {} \n\t\tQk1: {} \n\t\tQi2: {} \n\t\tQj2: {} \n\t\tQk2: {} \n\t\tQi3: {} \n\t\tQj3: {}  \n\t\tQk3: {} \n\t\t"
			.format(timestamp3, qi1,qj1,qk1, qi2, qj2, qk2, qi3, qj3, qk3))
			#scrittura sul file che registra tutti i dati 
			file_valori_sensori.write ("Valore dati nel sensor fusion compact: {}\n\t\tQi1: {}\n\t\tQj1: {}\n\t\tQk1: {}\n\t\tQi2: {} \n\t\tQj2: {} \n\t\tQk2: {} \n\t\tQi3: {} \n\t\tQj3: {}  \n\t\tQk3: {} \n".format(timestamp3, qi1,qj1,qk1, qi2, qj2, qk2, qi3, qj3, qk3))
			#scrittura sul file che registra i dati del sensor fusion necessari a MATLAB
			file_sensor_fusion =  open(nome_file_sensor_fusion_matlab, 'a+')
			file_sensor_fusion.write("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(timestamp3, time_formato_matlab, qi1,qj1,qk1, qi2, qj2, qk2, qi3, qj3, qk3))
			file_sensor_fusion.close()
			
		#se l'handle "cHandle" passato a handleNotification è quello corrispondente al sensor fusion compact
		if (cHandle == handle_mychar):
			#salvataggio del pacchetto ricevuto in una variabile ausiliaria
			newvalue = data
			print("\t\tValore ricevuto caratteristica pitch e roll: ",str(binascii.hexlify(newvalue), 'ascii').upper())
			file_valori_sensori.write("\t\tValore ricevuto nuova caratteristica: {}".format(str(binascii.hexlify(newvalue), 'ascii').upper()))
			#scomposizione del pacchetto ricevuto in timestamp (2 byte) e altri 2 dati da 2 byte ciascuno secondo il file "Getting started with the BlueST protocol and SDK.pdf"
			timestamp4, pitch, roll = unpack('<Hhh', newvalue)
			#conversione da radianti a gradi
			pitch = pitch / 8192 * 180 / math.pi
			roll = roll / 8192 * 180 / math.pi
			print("\t\tTimestamp: {}\n\t\tPitch: {} °\n\t\tRoll: {} °\n\t\t".format(timestamp4, pitch, roll))
			#scrittura sul file che registra tutti i dati 
			file_valori_sensori.write ("Valore dati catatteristica pitch e roll: {}\n\t\tPitch: {}\n\t\tRoll: {}\n".format(timestamp4, pitch, roll))
			#scrittura sul file che registra i dati della nuova caratteristica necessari a MATLAB
			file_nuova_caratteristica =  open(nome_file_nuova_caratteristica, 'a+')
			file_nuova_caratteristica.write("{}\t{}\t{}\t{}\n".format(timestamp4, time_formato_matlab, pitch, roll))
			file_nuova_caratteristica.close()
			
			
	def handleDiscovery(self, scanEntry, isNewDev, isNewData):
		DBG("Discovered device", scanEntry.addr)

class BluepyHelper:
	def __init__(self):
		self._helper = None
		self._poller = None
		self._stderr = None
		self.delegate = DefaultDelegate()

	def withDelegate(self, delegate_):
		self.delegate = delegate_
		return self

	def _startHelper(self,iface=None):
		if self._helper is None:
			DBG("Running ", helperExe)
			self._stderr = open(os.devnull, "w")
			args=[helperExe]
			if iface is not None: args.append(str(iface))
			self._helper = subprocess.Popen(args,
											stdin=subprocess.PIPE,
											stdout=subprocess.PIPE,
											stderr=self._stderr,
											universal_newlines=True,
											preexec_fn = preexec_function)
			self._poller = select.poll()
			self._poller.register(self._helper.stdout, select.POLLIN)

	def _stopHelper(self):
		if self._helper is not None:
			DBG("Stopping ", helperExe)
			self._poller.unregister(self._helper.stdout)
			self._helper.stdin.write("quit\n")
			self._helper.stdin.flush()
			self._helper.wait()
			self._helper = None
		if self._stderr is not None:
			self._stderr.close()
			self._stderr = None

	def _writeCmd(self, cmd):
		if self._helper is None:
			raise BTLEInternalError("Helper not started (did you call connect()?)")
		DBG("Sent: ", cmd)
		self._helper.stdin.write(cmd)
		self._helper.stdin.flush()

	def _mgmtCmd(self, cmd):
		self._writeCmd(cmd + '\n')
		rsp = self._waitResp('mgmt')
		if rsp['code'][0] != 'success':
			self._stopHelper()
			raise BTLEManagementError("Failed to execute management command '%s'" % (cmd), rsp)

	@staticmethod
	def parseResp(line):
		resp = {}
		for item in line.rstrip().split('\x1e'):
			(tag, tval) = item.split('=')
			if len(tval)==0:
				val = None
			elif tval[0]=="$" or tval[0]=="'":
				# Both symbols and strings as Python strings
				val = tval[1:]
			elif tval[0]=="h":
				val = int(tval[1:], 16)
			elif tval[0]=='b':
				val = binascii.a2b_hex(tval[1:].encode('utf-8'))
			else:
				raise BTLEInternalError("Cannot understand response value %s" % repr(tval))
			if tag not in resp:
				resp[tag] = [val]
			else:
				resp[tag].append(val)
		return resp

	def _waitResp(self, wantType, timeout=None):
		while True:
			if self._helper.poll() is not None:
				raise BTLEInternalError("Helper exited")

			if timeout:
				fds = self._poller.poll(timeout*1000)
				if len(fds) == 0:
					DBG("Select timeout")
					return None

			rv = self._helper.stdout.readline()
			DBG("Got:", repr(rv))
			if rv.startswith('#') or rv == '\n' or len(rv)==0:
				continue

			resp = BluepyHelper.parseResp(rv)
			if 'rsp' not in resp:
				raise BTLEInternalError("No response type indicator", resp)

			respType = resp['rsp'][0]
			if respType in wantType:
				return resp
			elif respType == 'stat':
				if 'state' in resp and len(resp['state']) > 0 and resp['state'][0] == 'disc':
					self._stopHelper()
					raise BTLEDisconnectError("Device disconnected", resp)
			elif respType == 'err':
				errcode=resp['code'][0]
				if errcode=='nomgmt':
					raise BTLEManagementError("Management not available (permissions problem?)", resp)
				elif errcode=='atterr':
					raise BTLEGattError("Bluetooth command failed", resp)
				else:
					raise BTLEException("Error from bluepy-helper (%s)" % errcode, resp)
			elif respType == 'scan':
				# Scan response when we weren't interested. Ignore it
				continue
			else:
				raise BTLEInternalError("Unexpected response (%s)" % respType, resp)

	def status(self):
		self._writeCmd("stat\n")
		return self._waitResp(['stat'])


class Peripheral(BluepyHelper):
	def __init__(self, deviceAddr=None, addrType=ADDR_TYPE_PUBLIC, iface=None):
		BluepyHelper.__init__(self)
		self._serviceMap = None # Indexed by UUID
		(self.deviceAddr, self.addrType, self.iface) = (None, None, None)

		if isinstance(deviceAddr, ScanEntry):
			self._connect(deviceAddr.addr, deviceAddr.addrType, deviceAddr.iface)
		elif deviceAddr is not None:
			self._connect(deviceAddr, addrType, iface)

	def setDelegate(self, delegate_): # same as withDelegate(), deprecated
		return self.withDelegate(delegate_)

	def __enter__(self):
		return self

	def __exit__(self, type, value, traceback):
		self.disconnect()

	def _getResp(self, wantType, timeout=None):
		if isinstance(wantType, list) is not True:
			wantType = [wantType]

		while True:
			resp = self._waitResp(wantType + ['ntfy', 'ind'], timeout)
			if resp is None:
				return None

			respType = resp['rsp'][0]
			if respType == 'ntfy' or respType == 'ind':
				hnd = resp['hnd'][0]
				data = resp['d'][0]
				if self.delegate is not None:
					self.delegate.handleNotification(hnd, data)
				if respType not in wantType:
					continue
			return resp

	def _connect(self, addr, addrType=ADDR_TYPE_PUBLIC, iface=None):
		if len(addr.split(":")) != 6:
			raise ValueError("Expected MAC address, got %s" % repr(addr))
		if addrType not in (ADDR_TYPE_PUBLIC, ADDR_TYPE_RANDOM):
			raise ValueError("Expected address type public or random, got {}".format(addrType))
		self._startHelper(iface)
		self.addr = addr
		self.addrType = addrType
		self.iface = iface
		if iface is not None:
			self._writeCmd("conn %s %s %s\n" % (addr, addrType, "hci"+str(iface)))
		else:
			self._writeCmd("conn %s %s\n" % (addr, addrType))
		rsp = self._getResp('stat')
		while rsp['state'][0] == 'tryconn':
			rsp = self._getResp('stat')
		if rsp['state'][0] != 'conn':
			self._stopHelper()
			raise BTLEDisconnectError("Failed to connect to peripheral %s, addr type: %s" % (addr, addrType), rsp)

	def connect(self, addr, addrType=ADDR_TYPE_PUBLIC, iface=None):
		if isinstance(addr, ScanEntry):
			self._connect(addr.addr, addr.addrType, addr.iface)
		elif addr is not None:
			self._connect(addr, addrType, iface)

	def disconnect(self):
		if self._helper is None:
			return
		# Unregister the delegate first
		self.setDelegate(None)

		self._writeCmd("disc\n")
		self._getResp('stat')
		self._stopHelper()

	def discoverServices(self):
		self._writeCmd("svcs\n")
		rsp = self._getResp('find')
		starts = rsp['hstart']
		ends   = rsp['hend']
		uuids  = rsp['uuid']
		nSvcs = len(uuids)
		assert(len(starts)==nSvcs and len(ends)==nSvcs)
		self._serviceMap = {}
		for i in range(nSvcs):
			self._serviceMap[UUID(uuids[i])] = Service(self, uuids[i], starts[i], ends[i])
		return self._serviceMap

	def getState(self):
		status = self.status()
		return status['state'][0]

	@property
	def services(self):
		if self._serviceMap is None:
			self._serviceMap = self.discoverServices()
		return self._serviceMap.values()

	def getServices(self):
		return self.services

	def getServiceByUUID(self, uuidVal):
		uuid = UUID(uuidVal)
		if self._serviceMap is not None and uuid in self._serviceMap:
			return self._serviceMap[uuid]
		self._writeCmd("svcs %s\n" % uuid)
		rsp = self._getResp('find')
		if 'hstart' not in rsp:
			raise BTLEGattError("Service %s not found" % (uuid.getCommonName()), rsp)
		svc = Service(self, uuid, rsp['hstart'][0], rsp['hend'][0])
		
		if self._serviceMap is None:
			self._serviceMap = {}
		self._serviceMap[uuid] = svc
		return svc

	def _getIncludedServices(self, startHnd=1, endHnd=0xFFFF):
		# TODO: No working example of this yet
		self._writeCmd("incl %X %X\n" % (startHnd, endHnd))
		return self._getResp('find')

	def getCharacteristics(self, startHnd=1, endHnd=0xFFFF, uuid=None):
		cmd = 'char %X %X' % (startHnd, endHnd)
		if uuid:
			cmd += ' %s' % UUID(uuid)
		self._writeCmd(cmd + "\n")
		rsp = self._getResp('find')
		nChars = len(rsp['hnd'])
		return [Characteristic(self, rsp['uuid'][i], rsp['hnd'][i],
							   rsp['props'][i], rsp['vhnd'][i])
				for i in range(nChars)]

	def getDescriptors(self, startHnd=1, endHnd=0xFFFF):
		self._writeCmd("desc %X %X\n" % (startHnd, endHnd) )
		# Historical note:
		# Certain Bluetooth LE devices are not capable of sending back all
		# descriptors in one packet due to the limited size of MTU. So the
		# guest needs to check the response and make retries until all handles
		# are returned.
		# In bluez 5.25 and later, gatt_discover_desc() in attrib/gatt.c does the retry
		# so bluetooth_helper always returns a full list.
		# This was broken in earlier versions.
		resp = self._getResp('desc')
		ndesc = len(resp['hnd'])
		return [Descriptor(self, resp['uuid'][i], resp['hnd'][i]) for i in range(ndesc)]

	def readCharacteristic(self, handle):
		self._writeCmd("rd %X\n" % handle)
		resp = self._getResp('rd')
		return resp['d'][0]

	def _readCharacteristicByUUID(self, uuid, startHnd, endHnd):
		# Not used at present
		self._writeCmd("rdu %s %X %X\n" % (UUID(uuid), startHnd, endHnd))
		return self._getResp('rd')

	def writeCharacteristic(self, handle, val, withResponse=False):
		# Without response, a value too long for one packet will be truncated,
		# but with response, it will be sent as a queued write
		cmd = "wrr" if withResponse else "wr"
		self._writeCmd("%s %X %s\n" % (cmd, handle, binascii.b2a_hex(val).decode('utf-8')))
		return self._getResp('wr')

	def setSecurityLevel(self, level):
		self._writeCmd("secu %s\n" % level)
		return self._getResp('stat')

	def unpair(self):
		self._mgmtCmd("unpair")

	def pair(self):
		self._mgmtCmd("pair")

	def setMTU(self, mtu):
		self._writeCmd("mtu %x\n" % mtu)
		return self._getResp('stat')

	def waitForNotifications(self, timeout):
		 resp = self._getResp(['ntfy','ind'], timeout)
		 return (resp != None)
	def _setRemoteOOB(self, address, address_type, oob_data, iface=None):
		if self._helper is None:
			self._startHelper(iface)
		self.addr = address
		self.addrType = address_type
		self.iface = iface
		cmd = "remote_oob " + address + " " + address_type
		if oob_data['C_192'] is not None and oob_data['R_192'] is not None:
			cmd += " C_192 " + oob_data['C_192'] + " R_192 " + oob_data['R_192']
		if oob_data['C_256'] is not None and oob_data['R_256'] is not None:
			cmd += " C_256 " + oob_data['C_256'] + " R_256 " + oob_data['R_256']
		if iface is not None:
			cmd += " hci"+str(iface)
		self._writeCmd(cmd)

	def setRemoteOOB(self, address, address_type, oob_data, iface=None):
		if len(address.split(":")) != 6:
			raise ValueError("Expected MAC address, got %s" % repr(address))
		if address_type not in (ADDR_TYPE_PUBLIC, ADDR_TYPE_RANDOM):
			raise ValueError("Expected address type public or random, got {}".format(address_type))
		if isinstance(address, ScanEntry):
			return self._setOOB(address.addr, address.addrType, oob_data, address.iface)
		elif address is not None:
			return self._setRemoteOOB(address, address_type, oob_data, iface)

	def getLocalOOB(self, iface=None):
		if self._helper is None:
			self._startHelper(iface)
		self.iface = iface
		self._writeCmd("local_oob\n")
		if iface is not None:
			cmd += " hci"+str(iface)
		resp = self._getResp('oob')
		if resp is not None:
			data = resp.get('d', [''])[0]
			if data is None:
				raise BTLEManagementError(
								"Failed to get local OOB data.")
			if ord(data[0]) != 8 or ord(data[1]) != 0x1b:
				raise BTLEManagementError(
								"Malformed local OOB data (address).")
			address = data[2:8]
			address_type = data[8:9]
			if ord(data[9]) != 2 or ord(data[10]) != 0x1c:
				raise BTLEManagementError(
								"Malformed local OOB data (role).")
			role = data[11:12]
			if ord(data[12]) != 17 or ord(data[13]) != 0x22:
				raise BTLEManagementError(
								"Malformed local OOB data (confirm).")
			confirm = data[14:30]
			if ord(data[30]) != 17 or ord(data[31]) != 0x23:
				raise BTLEManagementError(
								"Malformed local OOB data (random).")
			random = data[32:48]
			if ord(data[48]) != 2 or ord(data[49]) != 0x1:
				raise BTLEManagementError(
								"Malformed local OOB data (flags).")
			flags = data[50:51]
			return {'Address' : ''.join(["%02X" % ord(c) for c in address]),
					'Type' : ''.join(["%02X" % ord(c) for c in address_type]),
					'Role' : ''.join(["%02X" % ord(c) for c in role]),
					'C_256' : ''.join(["%02X" % ord(c) for c in confirm]),
					'R_256' : ''.join(["%02X" % ord(c) for c in random]),
					'Flags' : ''.join(["%02X" % ord(c) for c in flags]),
					}

	def __del__(self):
		self.disconnect()

class ScanEntry:
	addrTypes = { 1 : ADDR_TYPE_PUBLIC,
				  2 : ADDR_TYPE_RANDOM
				}

	FLAGS					 = 0x01
	INCOMPLETE_16B_SERVICES   = 0x02
	COMPLETE_16B_SERVICES	 = 0x03
	INCOMPLETE_32B_SERVICES   = 0x04
	COMPLETE_32B_SERVICES	 = 0x05
	INCOMPLETE_128B_SERVICES  = 0x06
	COMPLETE_128B_SERVICES	= 0x07
	SHORT_LOCAL_NAME		  = 0x08
	COMPLETE_LOCAL_NAME	   = 0x09
	TX_POWER				  = 0x0A
	SERVICE_SOLICITATION_16B  = 0x14
	SERVICE_SOLICITATION_32B  = 0x1F
	SERVICE_SOLICITATION_128B = 0x15
	SERVICE_DATA_16B		  = 0x16
	SERVICE_DATA_32B		  = 0x20
	SERVICE_DATA_128B		 = 0x21
	PUBLIC_TARGET_ADDRESS	 = 0x17
	RANDOM_TARGET_ADDRESS	 = 0x18
	APPEARANCE				= 0x19
	ADVERTISING_INTERVAL	  = 0x1A
	MANUFACTURER			  = 0xFF

	dataTags = {
		FLAGS					 : 'Flags',
		INCOMPLETE_16B_SERVICES   : 'Incomplete 16b Services',
		COMPLETE_16B_SERVICES	 : 'Complete 16b Services',
		INCOMPLETE_32B_SERVICES   : 'Incomplete 32b Services',
		COMPLETE_32B_SERVICES	 : 'Complete 32b Services',
		INCOMPLETE_128B_SERVICES  : 'Incomplete 128b Services',
		COMPLETE_128B_SERVICES	: 'Complete 128b Services',
		SHORT_LOCAL_NAME		  : 'Short Local Name',
		COMPLETE_LOCAL_NAME	   : 'Complete Local Name',
		TX_POWER				  : 'Tx Power',
		SERVICE_SOLICITATION_16B  : '16b Service Solicitation',
		SERVICE_SOLICITATION_32B  : '32b Service Solicitation',
		SERVICE_SOLICITATION_128B : '128b Service Solicitation',
		SERVICE_DATA_16B		  : '16b Service Data',
		SERVICE_DATA_32B		  : '32b Service Data',
		SERVICE_DATA_128B		 : '128b Service Data',
		PUBLIC_TARGET_ADDRESS	 : 'Public Target Address',
		RANDOM_TARGET_ADDRESS	 : 'Random Target Address',
		APPEARANCE				: 'Appearance',
		ADVERTISING_INTERVAL	  : 'Advertising Interval',
		MANUFACTURER			  : 'Manufacturer',
	}

	def __init__(self, addr, iface):
		self.addr = addr
		self.iface = iface
		self.addrType = None
		self.rssi = None
		self.connectable = False
		self.rawData = None
		self.scanData = {}
		self.updateCount = 0

	def _update(self, resp):
		addrType = self.addrTypes.get(resp['type'][0], None)
		if (self.addrType is not None) and (addrType != self.addrType):
			raise BTLEInternalError("Address type changed during scan, for address %s" % self.addr)
		self.addrType = addrType
		self.rssi = -resp['rssi'][0]
		self.connectable = ((resp['flag'][0] & 0x4) == 0)
		data = resp.get('d', [''])[0]
		self.rawData = data
		
		# Note: bluez is notifying devices twice: once with advertisement data,
		# then with scan response data. Also, the device may update the
		# advertisement or scan data
		isNewData = False
		while len(data) >= 2:
			sdlen, sdid = struct.unpack_from('<BB', data)
			val = data[2 : sdlen + 1]
			if (sdid not in self.scanData) or (val != self.scanData[sdid]):
				isNewData = True
			self.scanData[sdid] = val
			data = data[sdlen + 1:]

		self.updateCount += 1
		return isNewData
	 
	def _decodeUUID(self, val, nbytes):
		if len(val) < nbytes:
			return None
		bval=bytearray(val)
		rs=""
		# Bytes are little-endian; convert to big-endian string
		for i in range(nbytes):
			rs = ("%02X" % bval[i]) + rs
		return UUID(rs)

	def _decodeUUIDlist(self, val, nbytes):
		result = []
		for i in range(0, len(val), nbytes):
			if len(val) >= (i+nbytes):
				result.append(self._decodeUUID(val[i:i+nbytes],nbytes))
		return result
	
	def getDescription(self, sdid):
		return self.dataTags.get(sdid, hex(sdid))

	def getValue(self, sdid):
		val = self.scanData.get(sdid, None)
		if val is None:
			return None
		if sdid in [ScanEntry.SHORT_LOCAL_NAME, ScanEntry.COMPLETE_LOCAL_NAME]:
			try:
				# Beware! Vol 3 Part C 18.3 doesn't give an encoding. Other references
				# to 'local name' (e.g. vol 3 E, 6.23) suggest it's UTF-8 but in practice
				# devices sometimes have garbage here. See #259, #275, #292.
				return val.decode('utf-8')
			except UnicodeDecodeError:
				bbval = bytearray(val)
				return ''.join( [ (chr(x) if (x>=32 and x<=127) else '?') for x in bbval ] )
		elif sdid in [ScanEntry.INCOMPLETE_16B_SERVICES, ScanEntry.COMPLETE_16B_SERVICES]:
			return self._decodeUUIDlist(val,2)
		elif sdid in [ScanEntry.INCOMPLETE_32B_SERVICES, ScanEntry.COMPLETE_32B_SERVICES]:
			return self._decodeUUIDlist(val,4)
		elif sdid in [ScanEntry.INCOMPLETE_128B_SERVICES, ScanEntry.COMPLETE_128B_SERVICES]:
			return self._decodeUUIDlist(val,16)
		else:
			return val

	def getValueText(self, sdid):
		val = self.getValue(sdid)
		if val is None:
			return None
		if sdid in [ScanEntry.SHORT_LOCAL_NAME, ScanEntry.COMPLETE_LOCAL_NAME]:
			return val
		elif isinstance(val, list):
			return ','.join(str(v) for v in val)
		else:
			return binascii.b2a_hex(val).decode('ascii')
	
	def getScanData(self):
		'''Returns list of tuples [(tag, description, value)]'''
		return [ (sdid, self.getDescription(sdid), self.getValueText(sdid))
					for sdid in self.scanData.keys() ]
		 
 
class Scanner(BluepyHelper):
	def __init__(self,iface=0):
		BluepyHelper.__init__(self)
		self.scanned = {}
		self.iface=iface
		self.passive=False
	
	def _cmd(self):
		return "pasv" if self.passive else "scan"

	def start(self, passive=False):
		self.passive = passive
		self._startHelper(iface=self.iface)
		self._mgmtCmd("le on")
		self._writeCmd(self._cmd()+"\n")
		rsp = self._waitResp("mgmt")
		if rsp["code"][0] == "success":
			return
		# Sometimes previous scan still ongoing
		if rsp["code"][0] == "busy":
			self._mgmtCmd(self._cmd()+"end")
			rsp = self._waitResp("stat")
			assert rsp["state"][0] == "disc"
			self._mgmtCmd(self._cmd())

	def stop(self):
		self._mgmtCmd(self._cmd()+"end")
		self._stopHelper()

	def clear(self):
		self.scanned = {}

	def process(self, timeout=10.0):
		if self._helper is None:
			raise BTLEInternalError(
								"Helper not started (did you call start()?)")
		start = time.time()
		while True:
			if timeout:
				remain = start + timeout - time.time()
				if remain <= 0.0: 
					break
			else:
				remain = None
			resp = self._waitResp(['scan', 'stat'], remain)
			if resp is None:
				break

			respType = resp['rsp'][0]
			if respType == 'stat':
				# if scan ended, restart it
				if resp['state'][0] == 'disc':
					self._mgmtCmd(self._cmd())

			elif respType == 'scan':
				# device found
				addr = binascii.b2a_hex(resp['addr'][0]).decode('utf-8')
				addr = ':'.join([addr[i:i+2] for i in range(0,12,2)])
				if addr in self.scanned:
					dev = self.scanned[addr]
				else:
					dev = ScanEntry(addr, self.iface)
					self.scanned[addr] = dev
				isNewData = dev._update(resp)
				if self.delegate is not None:
					self.delegate.handleDiscovery(dev, (dev.updateCount <= 1), isNewData)
				 
			else:
				raise BTLEInternalError("Unexpected response: " + respType, resp)

	def getDevices(self):
		return self.scanned.values()

	def scan(self, timeout=10, passive=False):
		self.clear()
		self.start(passive=passive)
		self.process(timeout)
		self.stop()
		return self.getDevices()


def capitaliseName(descr):
	words = descr.replace("("," ").replace(")"," ").replace('-',' ').split(" ")
	capWords =  [ words[0].lower() ]
	capWords += [ w[0:1].upper() + w[1:].lower() for w in words[1:] ]
	return "".join(capWords)

class _UUIDNameMap:
	# Constructor sets self.currentTimeService, self.txPower, and so on
	# from names.
	def __init__(self, idList):
		self.idMap = {}

		for uuid in idList:
			attrName = capitaliseName(uuid.commonName)
			vars(self) [attrName] = uuid
			self.idMap[uuid] = uuid

	def getCommonName(self, uuid):
		if uuid in self.idMap:
			return self.idMap[uuid].commonName
		return None

def get_json_uuid():
	import json
	with open(os.path.join(script_path, 'uuids.json'),"rb") as fp:
		uuid_data = json.loads(fp.read().decode("utf-8"))
	for k in uuid_data.keys():
		for number,cname,name in uuid_data[k]:
			yield UUID(number, cname)
			yield UUID(number, name)

AssignedNumbers = _UUIDNameMap( get_json_uuid() )

if __name__ == '__main__':
	#if len(sys.argv) < 2:
	 #   sys.exit("Usage:\n  %s <mac-address> [random]" % sys.argv[0])

	if not os.path.isfile(helperExe):
		raise ImportError("Cannot find required executable '%s'" % helperExe)

	#mac-address del SensorTile
	devAddr = "c0:86:1d:31:45:48"
	#if len(sys.argv) == 3:
	addrType = "random"
	#else:
	 #	addrType = ADDR_TYPE_PUBLIC
	print("Connecting to: {}, address type: {}".format(devAddr, addrType))
	#creo un oggetto "Peripheral" ed effettuo una connessione al dispositivo indicato in devAdd (c0:83:1d:31:45:48)
	conn = Peripheral(devAddr, addrType)
	#ottengo l'ora attuale
	tempo = str(datetime.datetime.now())
	#definizione dei nomi dei file in cui sono salvati i dati ricevuti dal bluetooth
	nome_file_valori_sensori = "/home/matteo/Scrivania/MATLAB/Pitch e Roll/Dati sensori.txt"
	nome_file_sensor_fusion_matlab = "/home/matteo/Scrivania/MATLAB/Pitch e Roll/Sensor Fusion.txt"
	nome_file_accelerometro_matlab = "/home/matteo/Scrivania/MATLAB/Pitch e Roll/Accelerometro.txt"
	nome_file_giroscopio_matlab = "/home/matteo/Scrivania/MATLAB/Pitch e Roll/Giroscopio.txt"
	nome_file_magnetometro_matlab = "/home/matteo/Scrivania/MATLAB/Pitch e Roll/Magnetometro.txt"
	nome_file_nuova_caratteristica = "/home/matteo/Scrivania/MATLAB/Pitch e Roll/Pitch e roll.txt"
	#definizione dei byte da scrivere nel campo value del CCCD 
	notify_enable = bytes.fromhex('0100')
	indication_enable = bytes.fromhex('0200')
	notify_and_indication_enable = bytes.fromhex('0300')
	disable_notify_and_indication = bytes.fromhex('0000')
	#definizione degli uuid dei servizi e delle caratteristiche (presi dal file "Getting started with the BlueST protocol and SDK.pdf")
	uuid_services = ["00001801-0000-1000-8000-00805f9b34fb", "00001800-0000-1000-8000-00805f9b34fb", "00000000-0001-11e1-9ab4-0002a5d5c51b", 
	"00000000-000e-11e1-9ab4-0002a5d5c51b", "00000000-000f-11e1-9ab4-0002a5d5c51b", "00000000-0002-11e1-9ab4-0002a5d5c51b"]					
	
	uuid_characteristics = ["00000001-0001-11e1-ac36-0002a5d5c51b", "00000002-0001-11e1-ac36-0002a5d5c51b", "00000004-0001-11e1-ac36-0002a5d5c51b", "00000008-0001-11e1-ac36-0002a5d5c51b",
	"00000010-0001-11e1-ac36-0002a5d5c51b", "00000040-0001-11e1-ac36-0002a5d5c51b", "00000020-0001-11e1-ac36-0002a5d5c51b", "00000080-0001-11e1-ac36-0002a5d5c51b", 
	"00000100-0001-11e1-ac36-0002a5d5c51b","00000200-0001-11e1-ac36-0002a5d5c51b", "00000400-0001-11e1-ac36-0002a5d5c51b", "00000800-0001-11e1-ac36-0002a5d5c51b",
	"00001000-0001-11e1-ac36-0002a5d5c51b", "00002000-0001-11e1-ac36-0002a5d5c51b", "00004000-0001-11e1-ac36-0002a5d5c51b", "00008000-0001-11e1-ac36-0002a5d5c51b",
	"0x00010000-0001-11e1-ac36-0002a5d5c51b", "00020000-0001-11e1-ac36-0002a5d5c51b","00040000-0001-11e1-ac36-0002a5d5c51b", "00080000-0001-11e1-ac36-0002a5d5c51b",
	"00100000-0001-11e1-ac36-0002a5d5c51b", "00200000-0001-11e1-ac36-0002a5d5c51b", "00400000-0001-11e1-ac36-0002a5d5c51b", "00800000-0001-11e1-ac36-0002a5d5c51b",
	"01000000-0001-11e1-ac36-0002a5d5c51b", "02000000-0001-11e1-ac36-0002a5d5c51b", "04000000-0001-11e1-ac36-0002a5d5c51b", "08000000-0001-11e1-ac36-0002a5d5c51b",
	"10000000-0001-11e1-ac36-0002a5d5c51b", "20000000-0001-11e1-ac36-0002a5d5c51b", "40000000-0001-11e1-ac36-0002a5d5c51b", "80000000-0001-11e1-ac36-0002a5d5c51b",
	"00140000-0001-11e1-ac36-0002a5d5c51b", "00e00000-0001-11e1-ac36-0002a5d5c51b", "00002a05-0000-1000-8000-00805f9b34fb", "00002a00-0000-1000-8000-00805f9b34fb",
	"00002a01-0000-1000-8000-00805f9b34fb", "00002a04-0000-1000-8000-00805f9b34fb", "00000001-000e-11e1-ac36-0002a5d5c51b", "00000002-000e-11e1-ac36-0002a5d5c51b",
	"00000002-000f-11e1-ac36-0002a5d5c51b", "00ee0000-0001-11e1-ac36-0002a5d5c51b"]
	
	#ottengo una lista di oggetti "Characteristic" cercando tra le caratteristiche con handle compreso tra 0x00001 e 0xFFFF dalla periferica e con l'UUID specificato 
	ch_temp_press = conn.getCharacteristics (0X0001, 0XFFFF, "00140000-0001-11e1-ac36-0002a5d5c51b")[0]									#caratteristica temperatura e pressione
	ch_acc_gyr_magn = conn.getCharacteristics (0X0001, 0XFFFF, "00e00000-0001-11e1-ac36-0002a5d5c51b")[0]							#caratteristica accelerometro,giroscopio e magnetometro									
	ch_sensor_fusion_compact = conn.getCharacteristics (0X0001, 0XFFFF, "00000100-0001-11e1-ac36-0002a5d5c51b")[0]			#caratteristica sensor fusion compact
	ch_mychar = conn.getCharacteristics (0X0001, 0XFFFF, "00ee0000-0001-11e1-ac36-0002a5d5c51b")[0]											#caratteristica my characteristic
	#ottengo l'handle della caratteristica usata per identificare la relativa caratteristica
	#serve per capire quale caratteristica è relativa alla notifica ricevuta 
	handle_temp_press = ch_temp_press.getHandle()																						#handle caratteristica temperatura e pressione
	handle_acc_gyr_magn = ch_acc_gyr_magn.getHandle()																			#handle caratteristica accelerometro, giroscopio e magnetometro			
	handle_sensor_fusion_compact = ch_sensor_fusion_compact.getHandle()											#handle caratteristica sensor fusion compact	
	handle_mychar = ch_mychar.getHandle()																										#handle caratteristica my characteristic
	#ottengo una lista di oggetti "Descriptor" con UUID relativo al CCCD (0x2902).
	cccd_temp_press = ch_temp_press.getDescriptors(forUUID=0x2902)[0]													#descrittore della caratteristica temperatura e pressione
	cccd_acc_gyr_magn = ch_acc_gyr_magn.getDescriptors(forUUID=0x2902)[0]										#descrittore della caratteristica accelerometro, giroscopio e magnetometro
	cccd_sensor_fusion_compact = ch_sensor_fusion_compact.getDescriptors(forUUID=0x2902)[0]		#descrittore della caratteristica sensor fusion compact
	cccd_mychar = ch_mychar.getDescriptors(forUUID=0x2902)[0]																	#descrittore della caratteristica my characteristic
	
	#apertura del file che registra tutti i dati 
	with open(nome_file_valori_sensori, 'a+') as file_valori_sensori:
		#scrittura della data sul file che registra tutti i dati 
		file_valori_sensori.write("\nData: {}\n".format(datetime.datetime.now()))
		try:
			#input per scegliere quali notifiche abilitare
			scelta_temperatura_pressione = input ("Abilitare le notifiche di temperatura e pressione? (s/n) ")
			scelta_acc_giro_magn = input ("Abilitare le notifiche di accelerometro, giroscopio e magnetometro? (s/n) ")
			scelta_sensor_fusion_compact = input ("Abilitare le notifiche del sensor fusion compact? (s/n) ")
			scelta_pitch_roll = input ("Abilitare le notifiche della caratteristica del pitch e roll? (s/n) ")
			#controllo le scelte
			if (scelta_temperatura_pressione  == "s"):																						
				#abilitazione notifiche temperatura e pressione
				cccd_temp_press.write(notify_enable)
			elif (scelta_temperatura_pressione  == "n"):
				#disabilitazione notifiche temperatura e pressione
				cccd_temp_press.write(disable_notify_and_indication)
				#lettura pacchetto temperatura e pressione
				temp_press_value = ch_temp_press.read()
				print("\t\tValore ricevuto temperatura e pressione: ",str(binascii.hexlify(temp_press_value), 'ascii').upper())
				#scomposizione del pacchetto ricevuto in timestamp (2 byte), pressione (4 byte) e temperatura (2 byte)
				timestamp1, pressione, temperatura = unpack('<Hlh', temp_press_value)
				print ("\t\tTimestamp: {}\n\t\tPressione: {} mbar\n\t\tTemperatura: {} °C".format(timestamp1, pressione/100, temperatura/10))
				#scrittura sul file che registra tutti i dati 		
				file_valori_sensori.write("Valore temperatura e pressione: {}\n\t\tTimestamp: {}\n\t\tPressione: {} mbar\n\t\tTemperatura: {} °C\n".format(str(binascii.hexlify(temp_press_value), 'ascii').upper(), timestamp1, pressione/100, temperatura/10))
			else:
				print ("Scelta non corretta")

			if (scelta_acc_giro_magn == "s"):		
				#abilitazione notifiche accelerometro, giroscopio e magnetometro
				cccd_acc_gyr_magn.write(notify_enable)	
			elif (scelta_acc_giro_magn == "n"):		
				#disabilitazione notifiche accelerometro, giroscopio e magnetometro
				cccd_acc_gyr_magn.write(disable_notify_and_indication)				
				print("Dati da accelerometro, giroscopio e magnetometro non disponibili perchè le notifiche sono disattivate")
			else:
				print ("Scelta non corretta")
				
			if (scelta_sensor_fusion_compact == "s"):
				#abilitazione notifiche sensor fusion compact
				cccd_sensor_fusion_compact.write(notify_enable)						
			elif (scelta_sensor_fusion_compact == "n"):
				#disabilitazione notifiche sensor fusion compact
				cccd_sensor_fusion_compact.write(disable_notify_and_indication)		
				print("Dati dal sensor fusion non disponibili perchè le notifiche sono disattivate")				
			else:
				print ("Scelta non corretta")				
			
			if (scelta_pitch_roll == "s"):		
				#abilitazione notifiche nuova caratteristica
				cccd_mychar.write(notify_enable)	
			elif (scelta_acc_giro_magn == "n"):		
				#disabilitazione notifiche nuova caratteristica
				cccd_mychar.write(disable_notify_and_indication)				
				print("Dati della nuova caratteristica non disponibili perchè le notifiche sono disattivate")
			else:
				print ("Scelta non corretta")
				
			#se è stata abilitata almeno una notifica
			if (scelta_temperatura_pressione  == "s" or scelta_acc_giro_magn == "s" or scelta_sensor_fusion_compact == "s" or scelta_pitch_roll == "s"):						
				#ciclo per la gestione delle notifiche
				try:
					while True:
						timeout_notification = 1.0	
						if conn.waitForNotifications(timeout_notification):
							#chiamata della funzione handleNotification()				
							continue																																										
					print ("\t\tAspettando i dati...")
				#premere CTRL + C per uscire dal ciclo while True in cui si ricevono le notifiche 
				except KeyboardInterrupt:												
					print("\t\tInterruzione da tastiera")
				except BTLEException as e:
					print("\t\tErrore: ", e)					
					
		finally:
			#disconnessione dal SensorTile
			conn.disconnect()