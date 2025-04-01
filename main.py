
import network
import socket
import urequests
import time
import utime
import gc
import machine
import struct
import math
import os
import ina226
from time import sleep
from struct import unpack
from machine import Pin, I2C ,UART ,Timer
from umodbus.serial import Serial
from ota import OTAUpdater
from simple import MQTTClient

#pin
global led
led = machine.Pin("LED", machine.Pin.OUT)


pin_6 = Pin(6, mode=Pin.OUT)#WIFI & Camera
pin_7 = Pin(7, mode=Pin.OUT)#IV

pin_6.on()
pin_7.off()

print("Wait for Wifi 60 sec")
time.sleep(10)#wait for Wifi turn on


wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(pm = 0xa11140) # Diable powersave mode

#wlan.ifconfig(('10.42.0.3', '255.255.255.0', '10.42.0.1', '1.1.1.1'))

ssid = 'LUFTQI' 
password = '82767419'

#ssid = 'solarsdgs' 
#password = '82767419'

#solarsdgs_6001_MQTT
def mqtt_init():
    CLIENT_ID = "picow6001"
    client = MQTTClient(CLIENT_ID, '192.168.50.229',user=b"solarsdgs6001",password=b"82767419",)
    #client.set_callback(sub_cb)
    client.connect(clean_session=False)
    #client.subscribe('led')
    return client

"""     
def sub_cb(topic, msg):
    print((topic, msg))
    if topic == b'led':
        if msg == b'on':
            led.on()
        if msg == b'off':
            led.off()
"""
"""
#INA226
global SHUNT_OHMS

SHUNT_OHMS = 0.1
i2c = I2C(0,scl=Pin(1), sda=Pin(0))
#i2c = I2C(1, scl=Pin(3), sda=Pin(2))

print('I2C SCANNER')
devices = i2c.scan()

if len(devices) == 0:
  print("No i2c device !")
else:
  print('i2c devices found:', len(devices))

  for device in devices:
    print("I2C address: ", device)


# ina226
def power_read():
    # Create current measuring object
    
    ina = ina226.INA226(i2c, int(devices[0]))
    inb = ina226.INA226(i2c, int(devices[1]))
    inc = ina226.INA226(i2c, int(devices[2]))
    
    ina.set_calibration()
    inb.set_calibration()
    inc.set_calibration()
    
    utime.sleep_ms(10)
    vg = ina.bus_voltage
    utime.sleep_ms(10) # Delay to avoid micropython error
    va = inb.bus_voltage
    utime.sleep_ms(10)
    vp = inc.bus_voltage
       
    pin_7.on()
    time.sleep(1)    
    #utime.sleep_ms(10) # Delay to avoid micropython error
    ig = ina.shunt_voltage*100000
    utime.sleep_ms(10) # Delay to avoid micropython error
    ia = inb.shunt_voltage*100000
    utime.sleep_ms(10) # Delay to avoid micropython error
    ip = inc.shunt_voltage*100000
        
    
    if vg <= 1:
        vg = 0
    if va <= 1:
        va = 0
    if vp <= 1:
        vp = 0  
    
    if ig <= 10:
        ig = 0
    if ia <= 10:
        ia = 0
    if ip <= 10:
        ip = 0 
    
    pg = ig * vg
    pa = ia * va
    pp = ip * vp
    
    
    print("Vg = %.3f" % vg ,", Ig = %.3f" % ig , ", Pg = %.2f" % pg)
    print("Va = %.3f" % va ,", Ia = %.3f" % ia , ", Pa = %.2f" % pa)
    print("Vp = %.3f" % vp ,", Ip = %.3f" % ip , ", Pp = %.2f" % pp)
    
    pin_7.off()

    return pg,pa,pp
"""

#NTP
def set_time():
    # Get the external time reference
    utime.sleep(3)
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]   
    ss = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    time.sleep(1)

    try:
        ss.settimeout(1)
        res = ss.sendto(NTP_QUERY, addr)
        msg = ss.recv(48)
 
    finally:
        ss.close()

    #Set our internal time
    val = struct.unpack("!I", msg[40:44])[0]
    tm = val - NTP_DELTA    
    t = time.gmtime(tm)
    #print (t[3])
    t3 = t[3] + 8
    t2 = t[2]
    if t3 >= 24 :
        t3 = t3 -24
        t2 = t2 +1
    else:
        t3 = t3

    rtc.datetime((t[0],t[1],t2,t[6]+1,t3,t[4],t[5],0))


#wifi connect
def wifi_connect(ssid,password):    
    
    wlan.connect(ssid,password)    
    wait = 60
    while wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        wait -= 1
        print('waiting for connection..%s' %wait)
        time.sleep(1)
 
    # Handle connection error
    if wlan.status() != 3:        
        print('network connection failed')
        machine.reset()
        
    else:
        print('connected')
        ip=wlan.ifconfig()[0]
        print('IP: ', ip)



#######################################main############################################
pg = 2
pa = 3
pp = 5

rtc = machine.RTC()
NTP_DELTA = 2208988800
host = "pool.ntp.org"

#reset from 20:05
sleep_hour = 19 
sleep_minute = 30
sleep_time = 36000
reset_hour = 12
reset_minute = 10


#wifi connect
time.sleep(0.5)
try:
    wifi_connect(ssid,password)
    wdt = machine.WDT(timeout=8000)
    wdt.feed()
except OSError as e: 
    print(e)
    machine.reset()    

#Set RTC
time.sleep(0.5)
wdt = machine.WDT(timeout=8000)
try:
    set_time()
except OSError as e: 
    print(e)
    machine.reset()
wdt.feed()

#MQTT connect
time.sleep(0.5)
wdt = machine.WDT(timeout=8000)
try:
    client = mqtt_init()
except OSError as e: 
    print(e)
    machine.reset()
wdt.feed()


#OTA
firmware_url = f"https://github.com/luftqi/solar_picow6001/refs/heads/main/"
ota_updater = OTAUpdater(firmware_url, "main.py")
ota_updater.download_and_install_update_if_available()


#Led toggle
timer = Timer()
def blink(timer):
    led.toggle()
    
timer.init(freq = 2.5, mode=Timer.PERIODIC, callback=blink)



while True:
    
    current_time = rtc.datetime() 
    timestamp = b"Ping{:02d} {:02d} {:02d} {:02d} {:02d} {:02d} {:02d} 0 ".format(current_time[0], current_time[1], current_time[2] , current_time[3] ,current_time[4], current_time[5], current_time[6])    
    #print(b"ping {}".format(current_time))
    print(timestamp)   
    
    #Sleep
    if current_time[4] == sleep_hour and current_time[5] == sleep_minute:     
        # Stop/disable the RP2040 watchdog timer
        # 0x40058000 = WATCHDOG_CTRL register, bit 30 is the ENABLE bit
        machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
        print("start sleep") 
        pin_6.off()
        pin_7.off()
        timer.deinit()
        wlan.disconnect()
        wlan.active(False)
        wlan.deinit()
        time.sleep(55)
        
        print("lightt sleep")
                       
        #soft counter & sleep
        i = 0
        for i in range(1,sleep_time) :
            i = i + 1
            time.sleep(1)
            print(i)
            if i == sleep_time :
                time.sleep(60)
                print("wake up")                
                wlan = network.WLAN(network.STA_IF)
                wlan.active(True)
                #wlan.ifconfig(('10.42.0.3', '255.255.255.0', '10.42.0.1', '1.1.1.1'))
                time.sleep(0.5)
                try:
                    wifi_connect(ssid,password)
                    wdt = machine.WDT(timeout=8000)
                    wdt.feed()
                except OSError as e: 
                    print(e)
                    machine.reset()
                
                time.sleep(1)
                wdt = machine.WDT(timeout=8000)
                try:
                    BLYNK = Blynk(blynk_auth, insecure=True)
                    #BLYNK = Blynk(blynk_auth)
                except OSError as e: 
                    print(e) 
                    time.sleep(5)
                    machine.reset()
                wdt.feed()
                timer.init(freq = 2.5, mode=Timer.PERIODIC, callback=blink)
    
    #reset            
    if current_time[4] == reset_hour and current_time[5] == reset_minute:   
        machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
        time.sleep(55)
        machine.reset()
    
    
    print('network status:%d' % wlan.status()) 
    # wifi connect fail
    if wlan.status() != 3:        
        print('network connection failed')
        machine.reset()
        #raise RuntimeError('network connection failed')          
    
    wdt = machine.WDT(timeout=8000)
    #pg,pa,pp = power_read()
    mqtt_message = "%s_%s_%s" %(pg,pa,pp)
    print(mqtt_message)
    
    #mqtt_message= str(pg+"_"+pa+"_"+pp)
    client.publish('pg_pa_pp', mqtt_message)      
    wdt.feed()
    
    # Stop/disable the RP2040 watchdog timer
    # 0x40058000 = WATCHDOG_CTRL register, bit 30 is the ENABLE bit
    machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
    time.sleep(13)
    
    
   