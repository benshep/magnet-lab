from time import sleep
import serial
ser = serial.Serial()
ser.port = 'COM1'
ser.bytesize = 7
ser.parity = serial.PARITY_EVEN
ser.open()
ser.write(b'10mr0\r\n')
sleep(0.1)
reply = ser.read_all().decode('utf-8').splitlines()
print(reply)
ser.close()
