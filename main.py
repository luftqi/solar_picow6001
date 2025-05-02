import network
import socket
import urequests
import time
import utime
import ntptime
import gc
import machine
import struct
import math
import os
import ina226
import ujson
import select
from time import sleep
from struct import unpack
from machine import Pin, I2C ,UART ,Timer
from umodbus.serial import Serial
from ota import OTAUpdater
from simple import MQTTClient


#device
iot = "6001"

#wifi wait
wifi_wait_time = 60

#pin
global led
led = machine.Pin("LED", machine.Pin.OUT)
led.on()

pin_6 = Pin(6, mode=Pin.OUT)#PIZERO
pin_7 = Pin(7, mode=Pin.OUT)#IV

    
pin_6.on() #ON PIZERO啟動  OFF PIZERO關閉
pin_7.off()

#ssid = b'LUFTQI'
#password = b'82767419'

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(pm = 0xa11140) # Diable powersave mode
networks = wlan.scan()

ssid = b'solarsdgs'+iot 
password = b'82767419'
#ssid = b'Agromeans' 
#password = b'90339756'
#ssid = b'LUFTQI' 
#password = b'82767419'


#======================================
 
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


# read INA 226 dara
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
    
    pg = int(ig * vg)
    pa = int(ia * va) #calibration 
    pp = int(ip * vp)  
    
    print("Vg = %.3f" % vg ,", Ig = %.3f" % ig , ", Pg = %d" % pg)
    print("Va = %.3f" % va ,", Ia = %.3f" % ia , ", Pa = %d" % pa)
    print("Vp = %.3f" % vp ,", Ip = %.3f" % ip , ", Pp = %d" % pp)
    
    pin_7.off()

    return pg,pa,pp

rtc = machine.RTC()
rtc.datetime((2000, 1, 1, 0, 0, 0, 00, 0))
print(time.localtime())
# (date(2000, 1, 1) - date(1900, 1, 1)).days * 24*60*60
# (date(1970, 1, 1) - date(1900, 1, 1)).days * 24*60*60
NTP_DELTA = 3155673600 if time.gmtime(0)[0] == 2000 else 2208988800
# The NTP host can be configured at runtime by doing: ntptime.host = 'myhost.org'
host = "clock.stdtime.gov.tw"

def set_time(hrs_offset=0):  # Local time offset in hrs relative to UTC
    
    ntptime.NTP_DELTA = NTP_DELTA
    ntptime.host = host
    ntptime.settime() 
    now_time= time.localtime((time.time()+hrs_offset*3600))
    rtc.datetime((now_time[0],now_time[1],now_time[2],now_time[6],now_time[3],now_time[4],now_time[5],now_time[7]))

#wifi connect
def wifi_connect(ssid,password):    
    
    wlan.connect(ssid,password)    
    wait = 30
    while wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            print('network status:%d' % wlan.status()) 
            time.sleep(1)
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

#=====================================================================

# MQTT Parameters
#MQTT_SERVER = '10.247.134.2'
MQTT_SERVER = '10.42.0.1'
#MQTT_SERVER = '192.168.50.3'
MQTT_PORT = 0
MQTT_USER = b"solarsdgs"+iot
MQTT_PASSWORD = b"82767419"
MQTT_CLIENT_ID = b'solarsdgs'+iot+'_1'#must different id
MQTT_KEEPALIVE = 7200
MQTT_SSL = False   # set to False if using local Mosquitto MQTT broker

topic_pub = b'pg_pa_pp'
topic_sub = b'pizero2onoff'
#topic_msg = b''

def connect_mqtt():
    try:
        client = MQTTClient(client_id=MQTT_CLIENT_ID,
                            server=MQTT_SERVER,
                            port=MQTT_PORT,
                            user=MQTT_USER,
                            password=MQTT_PASSWORD,
                            keepalive=MQTT_KEEPALIVE)
        client.connect()
        return client
    except Exception as e:
        print('Error connecting to MQTT:', e)
        raise  # Re-raise the exception to see the full traceback

def reconnect_mqtt():
    print('Failed to connect to the MQTT Broker. Reconnecting...')
    time.sleep(1)
    try:
        client = MQTTClient(client_id=MQTT_CLIENT_ID,
                            server=MQTT_SERVER,
                            port=MQTT_PORT,
                            user=MQTT_USER,
                            password=MQTT_PASSWORD,
                            keepalive=MQTT_KEEPALIVE)
        client.disconnect()
        time.sleep(1)
        client.connect()
    except:
        pass
    print('Connected to %s MQTT Broker'%(MQTT_SERVER))
    return client

def publish_mqtt(topic, value):
    client.publish(topic, value)
    print(topic)
    print(value)
    print("Publish to topic" ,topic)

# Subcribe to MQTT topics
def subscribe(client, topic):
    client.subscribe(topic)
    print('Subscribe to topic:', topic)
    
# Callback function that runs when you receive a message on subscribed topic
def my_callback(topic, message):
    # Perform desired actions based on the subscribed topic and response
    print('Received message on topic:', topic)
    print('Response:', message)
    # Check the content of the received message
    message = message.decode('utf-8')
    print(message)
    msg = message.split('_')
    
    global pizero2_on
    global pizero2_off

    pizero2_on = int(msg[0])
    pizero2_off = int(msg[1])#轉int
    
    #防止大小錯誤
    if pizero2_on <= pizero2_off :
        pass
    else :
        pizero2_off2 = pizero2_on
        pizero2_on2 =pizero2_onf
        pizero2_on = pizero2_on                                                                    
        pizero2_off = pizero2_off2
    
    print("Recieve Pizero2on %d" % pizero2_on)
    print("Recieve Pizero2off %d" % pizero2_off)
    
    f1 = open("pizero2on.txt", "w")
    f1.write("%d" % pizero2_on)
    f1.close()  
    f2 = open("pizero2off.txt", "w")
    f2.write("%d" % pizero2_off)
    f2.close()
    global msgg  #判斷MQTT是否傳輸成功  成功則刪除掉DATA資料
    msgg = ""
    print("len(megg) : %d" % len(msgg))    


#######################################main############################################
        
pg = 1
pa = 1
pp = 1
old_data = "" 

#sleep from 19:00 to 18:00
sleep_hour = 19 
sleep_minute = 00
sleep_time = 39600

#reset at 12:10
reset_hour = 12
reset_minute = 10

#Data reset test key
msgg = "11"

#PZERO2 on/off

f1 = open("pizero2on.txt", "r")
f2 = open("pizero2off.txt", "r")
pizero2_on = int(f1.read())
pizero2_off = int(f2.read()) 


#Led toggle
timer = Timer()
def blink(timer):
    led.toggle()    


print("Wait for Wifi %d" % wifi_wait_time)

#wifi connect
time.sleep(wifi_wait_time) 

try:
    print("Start Wifi")
    wifi_connect(ssid,password)
except OSError as e: 
    print(e)
    machine.reset()    
        
#Set RTC
time.sleep(0.5)
for i in range(60):
    try :
        print("Set NTP & RTC")
        set_time(8)
        
        break
    except OSError as e:
        print(e)
        print("Waiting NTP connection")
        time.sleep(1)
else:
    machine.reset()
    
#ota
     
time.sleep(2)
print("Connect Github OTA")
firmware_url = f"https://github.com/luftqi/solar_picow{iot}/refs/heads/main/"
print(firmware_url)
try:
    ota_updater = OTAUpdater(firmware_url, "main.py")
    ota_updater.download_and_install_update_if_available()
except OSError as e:
    print(e)
    pass

while True:    
    
    gc.enable()
    gc.collect()
    print("Pizero2on / Pizero2off : %d / %d" %(pizero2_on ,pizero2_off))
    print(time.localtime())    
    current_time = time.localtime()
    #print(b"ping {}".format(current_time))
    #Python & MIcropython mktime is different
    nowtimestamp = "%s_%s_%s_%s_%s_%s" %(current_time[0],current_time[1],current_time[2],current_time[3],current_time[4],current_time[5])
    #nowtimestamp = int(time.mktime(current_time))-28800
        
    if int(current_time[4]) >= pizero2_on and int(current_time[4]) <= pizero2_off:  #>= turn on
               
        # Stop/disable the RP2040 watchdog timer
        # 0x40058000 = WATCHDOG_CTRL register, bit 30 is the ENABLE bit
        #machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
        #picow2 watch dog stop2
        machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)                
        pin_6.on()
        timer.init(freq = 2.5, mode=Timer.PERIODIC, callback=blink)#led toggle
        
        if wlan.isconnected() == False:
            print("Wait for Wifi %d" % wifi_wait_time)
            #wifi connect
            time.sleep(wifi_wait_time) 
        
            try:
                print("Start Wifi")
                wifi_connect(ssid,password)
            except OSError as e: 
                print(e)
                machine.reset()
            
        print ("Pizero on test")        
        
        time.sleep(1)
        for i in range(60):
            try :
                print("MQTT connect")
                client = connect_mqtt()
                client.set_callback(my_callback)
                subscribe(client, topic_sub)      
                break
            except OSError as e:
                print(e)
                print(wlan.status())
                print("Waiting MQTT reconnection")
                time.sleep(1)
            else:
                machine.reset()
        
        while True:
            current_time = time.localtime()
            #print(b"ping {}".format(current_time))
            #Python & MIcropython mktime is different
            #nowtimestamp = int(time.mktime(current_time))-28800 
            nowtimestamp = "%s_%s_%s_%s_%s_%s" %(current_time[0],current_time[1],current_time[2],current_time[3],current_time[4],current_time[5])        
            wdt = machine.WDT(timeout=8000)
            
            if int(current_time[4]) >= pizero2_on and int(current_time[4]) <= pizero2_off:     
                pg ,pa ,pp= power_read()
                #pg =100
                #pa =300
                #pp =300
                mqtt_message_in = "%s/%s/%s/%s" %(nowtimestamp,pg,pa,pp)   
                client.check_msg()
                # wifi connect fail hard restart
                
                if wlan.status() != 3:        
                    
                    print("Network offline")
                    timer.deinit()
                    wlan.disconnect()
                    wlan.active(False)
                    wlan.deinit()
                    time.sleep(58)
                    print("network hard restart")                
                    wlan = network.WLAN(network.STA_IF)
                    wlan.active(True)
                    wlan.config(pm = 0xa11140) # Diable powersave mode
                    time.sleep(0.5)
                    wifi_connect(ssid,password)      
            
                if 'data.txt' in os.listdir():  
                    with open('data.txt' , 'r' ,encoding = 'UTF-8') as f:
                        old_data = f.read()
                        print("Mqtt message in: %s" % mqtt_message_in)
                        lea = len(old_data)
                        new_data = '"'+old_data[1:(lea-1)]+mqtt_message_in+',"'
                        #print(new_data)
                        f.close()
                    
                    with open('data.txt' , 'w' , encoding = 'UTF-8') as f:                      
                        f.write(new_data)
                        f.close()  
                  
                    print ("len(msgg) :%d "% len(msgg))  
                    
                    if len(msgg)==0:     #test MQTT sucess than clear data                                                                
                        with open('data.txt' , 'w' , encoding = 'UTF-8') as f:                      
                            f.write("")
                            f.close()
                            print("Data reset!!") 
                            msgg ="11"
                    else :
                        pass
                else :
                    with open('data.txt' , 'w' , encoding = 'UTF-8') as f:                      
                        f.write("")
                        f.close()
                        print("Data.txt create!!")                   
            else:
                pin_6.off()
                break

            
            try :
                # Publish as MQTT payload
                time.sleep(1)                
                publish_mqtt(topic_pub, new_data)
            except OSError as e:
                print("push MQTT fail")
                print(wlan.status())
                print(e)
                reconnect_mqtt()
                pass 
            
            time.sleep(1) # 如果沒有sleep  MQTT publish 會異常
        
            wdt.feed() 
            #picow watchdog stop
            #machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
            #picow2 watch dog stop2
            machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
            time.sleep(23)
       
    else:
        pin_6.off()
        print("Pizero2 off")
    
    #PICO Sleep
    wdt = machine.WDT(timeout=8000)      
    if int(current_time[3]) == sleep_hour and int(current_time[4]) == sleep_minute:     
        #picow watchdog stop
        #machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
        #picow2 watch dog stop2
        machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
        
        pin_6.off()#sleep        
        timer.deinit()
        wlan.disconnect()
        wlan.active(False)
        wlan.deinit()
        time.sleep(55)        
        print("Start light sleep")

        #soft counter & sleep
        for i in range(0,sleep_time) :
            time.sleep(1)
            print(i)
            
            if i == sleep_time :
                pin_6.on()#wakeup
                time.sleep(60)
                print("wake up")                
                wlan = network.WLAN(network.STA_IF)
                wlan.active(True)
                wlan.config(pm = 0xa11140) # Diable powersave mode
                time.sleep(0.5)
                try:
                    wifi_connect(ssid,password)
                    print("Start wifi")
                except OSError as e: 
                    print(e)
                    machine.reset()
                
                time.sleep(1)
                timer.init(freq = 2.5, mode=Timer.PERIODIC, callback=blink)
    
    print("Restart test")
    
    #Picoreset            
    if int(current_time[3]) == reset_hour and int(current_time[4]) == reset_minute:   
        #picow watchdog stop
        #machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
        #picow2 watch dog stop2
        machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
        time.sleep(55)
        machine.reset()   


    pg ,pa ,pp= power_read()
    print("Power data read done!!")     
    #pg =10
    #pa =20
    #pp =20
    pin_6.off()
    mqtt_message_out = "%s/%s/%s/%s" %(nowtimestamp,pg,pa,pp) 
    print("MQTT message out : %s" %mqtt_message_out)
       
    
    if 'data.txt' in os.listdir():  
        with open('data.txt' , 'r' ,encoding = 'UTF-8') as f:
            old_data = f.read()
            #print(old_data)
            lea = len(old_data)
            new_data = '"'+old_data[1:(lea-1)]+mqtt_message_out+',"'
            #print(new_data)
            f.close()
        with open('data.txt' , 'w' , encoding = 'UTF-8') as f:                      
            f.write(new_data)
            f.close()
            print("Update Data done!!")

    else :
        with open('data.txt' , 'w' , encoding = 'UTF-8') as f:                      
            f.write("")
            f.close()
            print("Data.txt create!!")
    wdt.feed()
    # Stop/disable the RP2040 watchdog timer
    # 0x40058000 = WATCHDOG_CTRL register, bit 30 is the ENABLE bit

    #picow watchdog stop
    #machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
    #picow2 watch dog stop2
    machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
    time.sleep(23)
    gc.disable()
    
     

