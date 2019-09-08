import time
from bluepy.btle import Scanner, DefaultDelegate

class ScanDelegate(DefaultDelegate):                      				    #bluepy functions which receive Bluetooth messages asynchronously
																								#- such as notifications, indications, and advertising data - pass this information
																								#to the user by calling methods on a ‘delegate’ object.

	def __init__(self):                                   					 		    #To be useful, the delegate object will be from a class created by the user.
																								#Bluepy’s DefaultDelegate is a base class for this - you should override some or
																								#all of the methods here with your own application-specific code.
		DefaultDelegate.__init__(self)

	def handleDiscovery(self, dev, isNewDev, isNewData): 			#handleDiscovery is an instance method called when advertising data is received from an LE
																								#device while a Scanner object is active. 
		
		if isNewDev:					  								  				    #isNewDev is true if the device (as identified by its MAC address) has not been seen before by the scanner
			print ("Discovered device MAC address ", dev.addr)
		
		elif isNewData:					 							   					#isNewData is true if new or updated advertising data is available.
                                                            
			print("Received new data from", dev.addr) 

scanner = Scanner().withDelegate(ScanDelegate())	  				    #withDelegate(delegate) is an instance method that stores a reference to a delegate object,
																								#which receives callbacks when broadcasts from devices are received.
		
timeout=10.0																				#timeout for scanning = 10 seconds

devices = scanner.scan(timeout)				    							#scan is an instance method scans for devices for the given timeout in seconds. 
																								#During this period, callbacks to the delegate object will be called.
																								#When the timeout ends, scanning will stop and the method will return a list (or a
																								#view on Python 3.x) of ScanEntry objects view on Python 3.x) of ScanEntry objects time.																						 

SensorTile_state=0																	#initialize the SensorTile as OFF
SensorTile_MACAddress="c0:83:1d:31:45:48"								#initialize the SensorTile MAC address
file_name="bluepyscanlog.txt"													#initialize the log file name 

with open(file_name, 'a+') as the_file:
	the_file.write("\nData: {}\n".format(time.ctime()))  						#write the time in log file

for dev in devices:
	if (dev.addr==SensorTile_MACAddress):									#searching for SensorTile (MAC ADDRESS=c0:83:1d:31:45:48), true if SensorTile is on, false if SensorTile is off
		SensorTile_state=1															#SensorTile is ON!
		
if (SensorTile_state==1):
	print("\nSensorTile is ON!\n")
else:
	print("\nSensorTile is OFF!\n")
	
for dev in devices:
	if(dev.addr==SensorTile_MACAddress):		
		print("\nDevice MAC address: {}\n	{}  address type\n	bluetooth interface number: /dev/hci{}\n	RSSI= {} dB\n	connectable: {}\n	number of advertising packets received: {}".format(dev.addr, dev.addrType, dev.iface, dev.rssi, dev.connectable, dev.updateCount))
																								#dev.addr: Device MAC address (as a hex string separated by colons).
																								#dev.addrType: one of ADDR_TYPE_PUBLIC or ADDR_TYPE_RANDOM.
																								#dev.iface: Bluetooth interface number (0 = /dev/hci0) on which advertising information was seen.
																								#dev.rssi: Received Signal Strength Indication
																								#dev.connectable: Boolean value - True if the device supports connections, and False otherwise (typically used for advertising ‘beacons’).
																								#dev.updateCount: Integer count of the number of advertising packets received from the device so far (since clear() was called on the Scanner object which found it).
		with open(file_name, 'a+') as the_file:
			the_file.write("\nDevice MAC address: {}\n	{}  address type\n	bluetooth interface number: /dev/hci{}\n	RSSI= {} dB\n	connectable: {}\n	number of advertising packets received: {}\n".format(dev.addr, dev.addrType, dev.iface, dev.rssi, dev.connectable, dev.updateCount))
		for (adtype, description, value) in dev.getScanData():			#getScanData is an instance method that returns a list of tuples (adtype, description, value)
																								#containing the advertising data type code, human-readable description and value 
																								#(as reported by getDescription() and getValueText()) for all available advertising data items.
																										
			print("	Advertising data: {}\n	Advertising data description: {}\n	Advertising data value: {}".format(adtype, description, value))			
																								#output print advertising data type, human-readable description and value		
			with open(file_name, 'a+') as the_file:
				the_file.write("	Advertising data: {}\n	Advertising data description: {}\n	Advertising data value: {}\n".format(adtype, description, value))
