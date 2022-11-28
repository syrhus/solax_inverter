# Python Plugin Solax inverter
#
# Created: 04-sept-2020
# Author: Syrhus
#
"""
<plugin key="solax_power" name="Solax Inverter" author="syrhus" version="1.2.2" externallink="https://github.com/syrhus/solax_inverter">
    <params>
        <param field="Address" label="IP Domoticz" width="250px" required="true"/>
        <param field="Port" label="Port Domoticz" width="100px" required="true"/>
        <param field="Mode1" label="TokenID" width="250px" required="true"/>
        <param field="Mode2" label="N°enregistrement(s) (si plusieurs, utiliser ',' pour séparer chaque onduleur)" width="300px" required="true"/>
        <param field="Mode3" label="Minutes avant/après le lever/coucher du soleil" width="50px" default="30" required="true"/>
	<param field="Mode4" label="Heure d'été(1=Oui, 0=Non)" width="50px" default="1" required="true"/>
        <param field="Mode5" label="Fréquence MaJ (min)" width="50px" required="true" default="5"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import requests
import datetime


#"https://www.eu.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do?tokenId={}&sn={}"
SOLAX_CLOUD_SITE = "www.eu.solaxcloud.com";
SOLAX_CLOUD_PORT = "9443";
SOLAX_API = "/proxy/api/getRealtimeInfo.do";
SOLAX_CMD = "?tokenId={}&sn={}";

SOLAX_CURRENT = "acpower";
SOLAX_SUM = "yieldtoday";
SOLAX_TIME = "uploadTime";
SERIAL_NUMBER = "sn";

class BasePlugin:
    enabled = False
    def __init__(self):
        self.heartbeat = 0
        self.cmds = list()
        self.currents = []
        self.cumuls = []
        self.invertersSN = list()
        self.timedelta = 30
        self.previousState = None
        self.summerTime = 1
        return

    def url(self, json_cmd):
        return 'http://' + Parameters["Address"] + ':'+ Parameters["Port"] + json_cmd

    def request(self, cmd):
        Domoticz.Debug(f"url:{cmd}")
        response = requests.get(cmd)
        Domoticz.Debug(f"response:{response}")
        if response.ok:
            response.connection.close()
            return response.json()

    def parseURL(self, Parameter):
        return 'https://' + SOLAX_CLOUD_SITE + ':' +SOLAX_CLOUD_PORT + SOLAX_API + SOLAX_CMD.format(Parameters["Mode1"], Parameter)

    def onStart(self):
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
               
        DumpConfigToLog()
        
        #default value
        self.sunrise = datetime.time(7,30,0)
        self.sunrise = datetime.time(21,30,0)
                      
        self.freq = int(Parameters["Mode5"])
        if(self.freq<1):
            Domoticz.Log("La fréquence de lecture des données ne peut pas être inférieure à 1 min")
            return
        
        Domoticz.Heartbeat(30)    
        self.beatcount = self.freq*2
        Domoticz.Debug("beatcount :" + str(self.beatcount))
        
        self.timedelta = int(Parameters["Mode3"])
        self.summerTime = int(Parameters["Mode4"])
	
        self.addInverters()
                        
        self.getSunset()
        
        if (len(Devices) == 0):
            
            for idx,d in enumerate(self.invertersSN):
                Domoticz.Device(Name= self.invertersSN[idx] , Unit=idx+1,TypeName="kWh", Switchtype=4, Options={"EnergyMeterMode" : "0"}, Used = 1 ).Create() #TypeName="kWh"
                Domoticz.Log("Device " + Devices[idx+1].Name + " created")
                
            if(len(self.invertersSN)>1):
                Domoticz.Device(Name="Total", Unit=len(Devices)+1, TypeName="kWh", Switchtype=4, Options={"EnergyMeterMode" : "0"}, Used = 1).Create()          
                Domoticz.Log("Device " + Devices[len(Devices)].Name + " created")
                
        self.heartbeat = self.beatcount

    def getSunset(self):
        Domoticz.Debug('getSunset called')

        nbInverters = len(self.invertersSN)
        if(nbInverters > 1):
            nbInverters += 1
        
        self.currents = [0] * nbInverters
        self.cumuls = [0] * nbInverters
        self.timedOut= [False] * nbInverters

        self.currentDate = datetime.datetime.now().date()
        Domoticz.Debug("currentDate:" + str(self.currentDate))

        cmd = '/json.htm?type=command&param=getSunRiseSet'
        dJson = self.request(self.url(cmd))
        Domoticz.Debug("result:" + str(dJson))
        
        delta = datetime.timedelta(minutes=self.timedelta)
        self.sunrise = datetime.time(hour=int(dJson['Sunrise'].split(':')[0]),minute=int(dJson['Sunrise'].split(':')[1]),second=0)
        self.sunset = datetime.time(hour=int(dJson['Sunset'].split(':')[0]),minute=int(dJson['Sunset'].split(':')[1]),second=0) 
        
        self.sunrise = (datetime.datetime.combine(datetime.date(1, 1, 1), self.sunrise) - delta).time()
        self.sunset = (datetime.datetime.combine(datetime.date(1, 1, 1), self.sunset) + delta).time()

        Domoticz.Debug("sunrise:" + str(self.sunrise))
        Domoticz.Debug("sunset:" + str(self.sunset))

    def getData(self):
        for i,d in enumerate(self.invertersSN):
            dJson = self.request(self.cmds[i])
            Domoticz.Debug("result:" + str(dJson))
            
            if dJson["success"] :
                time = dJson["result"][SOLAX_TIME]
                Domoticz.Debug("uploadTime:" + time)
                
                #date_format = "%Y-%m-%d %H:%M:%S"
                #solax_date = datetime.datetime.strptime( time, date_format)
                date_split = time.split()[0].split('-')
                time_split = time.split()[1].split(':')
                solax_date = datetime.datetime(int(date_split[0]),int(date_split[1]), int(date_split[2]))
                solax_datetime = datetime.datetime(int(date_split[0]),int(date_split[1]), int(date_split[2]) , int(time_split[0])+ self.summerTime, int(time_split[1]), int(time_split[2]))
                
                time_delta = (datetime.datetime.now() - solax_datetime).total_seconds()
                
                Domoticz.Debug("DiffTime:" + str(time_delta))
                
                if self.currentDate != solax_date.date() or time_delta > (self.freq*60*2):
                    Domoticz.Log(Devices[i+1].Name + " (" + dJson["result"][SERIAL_NUMBER] + "):"+ time + " is obsolete")
                    #Devices[i+1].Update(nValue=0, sValue="0", TimedOut = 1)
                    self.timedOut[i] = True
                else:
                    self.timedOut[i] = False
                    self.currents[i] = int(dJson["result"][SOLAX_CURRENT])
                    self.cumuls[i] = int(float(dJson["result"][SOLAX_SUM])*1000)
            else:
                self.timedOut[i] = True

        self.updateDevices()
                   
    def addInverters(self):
        self.invertersSN = Parameters["Mode2"].split(',')
        for inverter in self.invertersSN:
            self.cmds.append(self.parseURL(inverter))

    def onStop(self):
        Domoticz.Log("Plugin is stopping.")
		    
    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("Status:" + str(Status))

    def onMessage(self, Connection, Data):
        Domoticz.Debug("Data:" + str(Data))

    def onDisconnect(self, Connection):
        Domoticz.Log("Device has disconnected")

    def checkStatus(self, newStatus):
        if self.previousState != newStatus:
            self.previousState = newStatus
            Domoticz.Status(newStatus)
            if newStatus == "Off":
                Domoticz.Log("Night time, no data to retrieve")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat called")
        now = datetime.datetime.now()
        
        Domoticz.Debug("now: " + str(now.date()))
        Domoticz.Debug("currentDate:" + str(self.currentDate))
        if self.currentDate < now.date():
            self.getSunset()
            return

        currentTime = now.time()
   		
        if currentTime > self.sunrise and currentTime < self.sunset:
            self.checkStatus("On")
            if self.heartbeat < self.beatcount:
                self.heartbeat = self.heartbeat + 1
                Domoticz.Debug("hearbeat:" + str(self.heartbeat))
            else:
                self.getData()
                self.heartbeat = 0
        else:       
            self.checkStatus("Off")
            

    def updateDevices(self):

        Domoticz.Debug("updateDevices called")
        nbInverters = len(self.invertersSN)
        Domoticz.Debug("nbInverters : " + str(nbInverters))
        if nbInverters > 1:

            self.currents[nbInverters] = 0
            self.cumuls[nbInverters] = 0


            for i,d in enumerate(self.invertersSN):
                #if(not self.timedOut[i]):
                self.cumuls[nbInverters]+=self.cumuls[i]
                Domoticz.Debug("self.cumuls[" + str(i) + "]= " + str(self.cumuls[i]) )
                Domoticz.Debug("self.cumuls[" + str(nbInverters) + "]= " + str(self.cumuls[nbInverters]) )
                self.currents[nbInverters]+=self.currents[i]
                Domoticz.Debug("self.currents[" + str(i) + "]= " + str(self.currents[i]) )
                Domoticz.Debug("self.currents[" + str(nbInverters) + "]= " + str(self.currents[nbInverters]) )

        for i,d in enumerate(Devices):
            if(not self.timedOut[i]):
                self.updateDevice(i+1)

    def updateDevice(self, Unit):
        Domoticz.Debug("updateDevice called " + str(Unit))
        # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
        if (Unit in Devices):
            strValue =  str(self.currents[Unit-1]) + ";" + str(self.cumuls[Unit-1])
            Domoticz.Debug("strValue :" + strValue)
            if(Devices[Unit].sValue != strValue):
                Devices[Unit].Update(nValue=0, sValue=strValue, TimedOut = 0)
                Domoticz.Log("Update ("+ Devices[Unit].Name + ") current="+ str(self.currents[Unit-1]) +"W  cumul="+ str(self.cumuls[Unit-1]) +"W")
        return            

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
            
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
                
    return
