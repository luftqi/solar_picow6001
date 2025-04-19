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
import ujson
from time import sleep
from struct import unpack
from machine import Pin, I2C ,UART ,Timer
from umodbus.serial import Serial
from ota import OTAUpdater
from simple import MQTTClient


#device
device = "6001"

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

ssid = b'solarsdgs' 
password = b'82767419'
#ssid = b'Agromeans' 
#password = b'90339756'

#MQTT publish

mqtt_server = '10.42.0.1'

client_id = 'solarsdgs%s_1' %device
topic_pub = b'pg_pa_pp'
topic_sub = b'pizero2onoff'
mqttuser=b"solarsdgs%s" %device
mqttpassword=b"82767419"
topic_msg = b''

def mqtt_connect():
    client = MQTTClient(client_id, mqtt_server,user = mqttuser,password =mqttpassword, keepalive=3600)
    try:
        client.connect()
        client.set_callback(sub_cb)
    except:
        pass
    
    print('Connected to %s MQTT Broker'%(mqtt_server))
    return client

def reconnect():
    print('Failed to connect to the MQTT Broker. Reconnecting...')
    time.sleep(1)
    try:
        client = MQTTClient(client_id, mqtt_server,user = mqttuser,password =mqttpassword, keepalive=3600)
        client.disconnect()
        time.sleep(1)
        client.connect()
        client.set_callback(sub_cb)
    except:
        pass
    print('Connected to %s MQTT Broker'%(mqtt_server))
    return client


#MQTT sub
def sub_cb(topic, msg):
    #print("New message on topic {}".format(topic.decode('utf-8')))
    
    msg = msg.decode('utf-8')
    print(msg)
    msg = msg.split('_')
    
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
        pizero2_on = pizero2_on2
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

#NTP
def set_time():
    # Get the external time reference
    time.sleep(1)
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]   
    ss = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    time.sleep(1)

    try:
        ss.settimeout(10)
        res = ss.sendto(NTP_QUERY, addr)
        msg = ss.recv(48)
 
    finally:
        ss.close()

    #Set our internal time
    val = struct.unpack("!I", msg[40:44])[0]
    tm = val - NTP_DELTA    
    t = time.gmtime(tm)
    #print (t[3])
    #t3 = t[3] + 8 #Taiwan UTC+8???
    t3 = t[3]
    t2 = t[2]
    if t3 >= 24 :
        t3 = t3 -24
        t2 = t2 +1
    else:
        t3 = t3
    print(t)
    machine.RTC().datetime((t[0],t[1],t2,t[6]+1,t3,t[4],t[5],0))

#wifi connect
def wifi_connect(ssid,password):    
    
    wlan.connect(ssid,password)    
    wait = 100
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

def pizero2on():
    
    global msgg,pa,pg,pp
    msgg = "11"
             
    print("Pizero2 start work!")
    #publish MQTT message & reset data.txt               
    while True :
        current_time = machine.RTC().datetime()
        nowtimestamp = time.mktime(time.localtime())
        if int(current_time[5]) >= pizero2_on and int(current_time[5]) <= pizero2_off:     
            #picow watchdog stop
            machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
            #picow watchdog stop
            #machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
            #print(b"ping {}".format(current_time))
            nowtimestamp = time.mktime(time.localtime())
            pg =2
            pa =2
            pp =2
            #pg ,pa ,pp= power_read()
            print("Power data read done!!")
            mqtt_message_in = "%s/%s/%s/%s" %(nowtimestamp,pg,pa,pp)   
  
            # wifi connect fail hard restart
            if wlan.status() != 3:        
                #picow watchdog stop
                machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
                #picow2 watch dog stop2
                #machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
                print("Network offline")
                pin_6.off()
                time.sleep(1)
                pin_6.on()                    
                time.sleep(90)
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
                    try :
                        client.publish(topic_pub, new_data)
                        client.subscribe(topic_sub)
                    except :
                        pass
                    
                    print("Push mqtt done!!")                   
                
                print ("len(msgg) :%d "% len(msgg))  
                    
                if len(msgg)==0:     #test MQTT sucess than clear data                                                                
                    with open('data.txt' , 'w' , encoding = 'UTF-8') as f:                      
                        f.write("")
                        f.close()
                        print("Data reset!!") 
                        msgg =""
                else :
                        pass
            else :
                    with open('data.txt' , 'w' , encoding = 'UTF-8') as f:                      
                        f.write("")
                        f.close()
                        print("Data.txt create!!")
                   
        else:
            break
            #picow watchdog stop
            machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
            #picow2 watch dog stop2
            #machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
            time.sleep(23)


def picosleepandrestart(current_time,sleep_time,ssid,password,reset_hour,resst_minute):
    if int(current_time[4]) == sleep_hour and int(current_time[5]) == sleep_minute:     
        #picow watchdog stop
        machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
        #picow2 watch dog stop2
        #machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
        
        pin_6.off()        
        timer.deinit()
        wlan.disconnect()
        wlan.active(False)
        wlan.deinit()
        time.sleep(55)        
        print("Start light sleep")

        #soft counter & sleep
        for i in range(0,sleep_time) :
            i = i + 1
            time.sleep(1)
            print(i)
            
            if i == sleep_time :
                pin_6.off()
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
    #reset            
    if int(current_time[4]) == reset_hour and int(current_time[5]) == reset_minute:   
        #picow watchdog stop
        machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
        #picow2 watch dog stop2
        #machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
        time.sleep(55)
        machine.reset() 


#######################################main############################################
        
pg = 1
pa = 1
pp = 1
old_data = "" 
rtc = machine.RTC()
NTP_DELTA = 2208988800
host = "pool.ntp.org"

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
        
time.sleep(1)
try:
    print("Set Rtc")
    set_time()
except OSError as e: 
    print(e)
    machine.reset()
    
#OTA
time.sleep(1)
try:
    print("Connect Github")
    
    firmware_url = "https://github.com/luftqi/solar_picow6001/refs/heads/main/"
    
    ota_updater = OTAUpdater(firmware_url, "main.py")
    ota_updater.download_and_install_update_if_available()
except OSError as e:
    print(e)
    machine.reset()    
        
#MQTT connect
time.sleep(1)
try:
    client = mqtt_connect()
except OSError as e:
    reconnect()


while True:    
    
    gc.enable()      
    print("Pizero2on / Pizero2off : %d / %d" %(pizero2_on ,pizero2_off))
    current_time = machine.RTC().datetime()
    #print(b"ping {}".format(current_time))
    nowtimestamp = time.mktime(time.localtime())
    
    if int(current_time[5]) >= pizero2_on and int(current_time[5]) <= pizero2_off:  #>= turn on
               
        # Stop/disable the RP2040 watchdog timer
        # 0x40058000 = WATCHDOG_CTRL register, bit 30 is the ENABLE bit
        machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
        #picow2 watch dog stop2
        #machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)                
        pin_6.on()
        timer.init(freq = 2.5, mode=Timer.PERIODIC, callback=blink)#led toggle
        
        print ("Pizero on test")        
        pizero2on()
       
    else:
        pin_6.off()
          
    print("Pico sleep test")
    picosleepandrestart(current_time,sleep_time,ssid,password,reset_hour,reset_minute)
     
    #pg ,pa ,pp= power_read()
    print("Power data read done!!")     
    pg =1
    pa =1
    pp =1
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
   
    # Stop/disable the RP2040 watchdog timer
    # 0x40058000 = WATCHDOG_CTRL register, bit 30 is the ENABLE bit
    #pico 2 w cannot stop watchdog
    #picow watchdog stop
    machine.mem32[0x40058000] = machine.mem32[0x40058000] & ~(1<<30)
    #picow2 watch dog stop2
    #machine.mem32[0x400d8000] = machine.mem32[0x400d8000] & ~(1<<30)
    time.sleep(23)
    gc.disable()
