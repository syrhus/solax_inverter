# Python Plugin Solax inverter
#
# Created: 04-sept-2020
# Author: Syrhus
#
"""
<plugin key="solax_power" name="Solax Inverter" author="syrhus" version="1.0.1" externallink="https://github.com/syrhus/solax_inverter">
    <params>
        <param field="Mode1" label="TokenID" width="250px" required="true"/>
        <param field="Mode2" label="N°enregistrement(s) (si plusieurs, utiliser ',' pour séparer chaque onduleur)" width="300px" required="true"/>
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
import json
import datetime

#"https://www.eu.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do?tokenId={}&sn={}"
SOLAX_CLOUD_SITE = "www.eu.solaxcloud.com"
SOLAX_CLOUD_PORT = "9443"
SOLAX_API = "/proxy/api/getRealtimeInfo.do"
SOLAX_CMD = "?tokenId={}&sn={}"

SOLAX_CURRENT = "acpower"
SOLAX_SUM = "yieldtoday"
SOLAX_TIME = "uploadTime"


class BasePlugin:
    enabled = False
    def __init__(self):
        self.heartbeat = 0
        self.currentInverter = 0
        self.cmds = list()
        self.currents = []
        self.cumuls = []
        self.invertersSN = list()
        self.httpConn = None
        return

    def parseURL(self, Parameter):
        return SOLAX_API + SOLAX_CMD.format(Parameters["Mode1"], Parameter)

    def getData(self, num = 0):

        self.currentInverter = num
        if(not(self.httpConn and (self.httpConn.Connected() or self.httpConn.Connecting()))):
            self.httpConn = Domoticz.Connection(Name="Solax", Transport="TCP/IP", Protocol="HTTPS", Address=SOLAX_CLOUD_SITE, Port=SOLAX_CLOUD_PORT)
            self.httpConn.Connect()
        else:
            self.sendData(self.httpConn)

                   
    def addInverters(self):
        self.invertersSN = Parameters["Mode2"].split(',')
        for inverter in self.invertersSN:
            self.cmds.append(self.parseURL(inverter))

        
    def onStart(self):

        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
               
        DumpConfigToLog()
        self.morning = datetime.time(7, 30, 0)
        self.night = datetime.time(21, 30, 0)
        
        freq = int(Parameters["Mode5"])
        if(freq<1):
            Domoticz.Log("La fréquence de lecture des données ne peut pas être inférieure à 1 min")
            return
        
        Domoticz.Heartbeat(20)    
        self.beatcount = freq*3#freq*6
        Domoticz.Debug("beatcount :" + str(self.beatcount))
        
        self.addInverters()

        nbInverters = len(self.invertersSN)
        Domoticz.Debug("Nb Inverters :" + str(nbInverters))
        
        if(nbInverters > 1):
            nbInverters += 1
            
        self.currents = [0] * nbInverters
        self.cumuls = [0] * nbInverters
        self.lasts= [None] * nbInverters
        
        if (len(Devices) == 0):
            
            for idx,d in enumerate(self.invertersSN):
                Domoticz.Device(Name= self.invertersSN[idx] , Unit=idx+1, TypeName="kWh", Used = 1).Create()
                Domoticz.Log("Device " + Devices[idx+1].Name + " created")
                
            if(len(self.invertersSN)>1):
                Domoticz.Device(Name="Total", Unit=len(Devices)+1, TypeName="kWh", Used = 1).Create()          
                Domoticz.Log("Device " + Devices[len(Devices)].Name + " created")
                
        self.heartbeat = self.beatcount
            
    def onStop(self):
        Domoticz.Log("Plugin is stopping.")
        
    def sendData(self, Connection):
        if(Connection.Connected):
            headers = dict({"Accept": "application/json", 
            "Content-Type": "application/json",
            #"Connection": "close",
            "Host":SOLAX_CLOUD_SITE + SOLAX_CLOUD_PORT})

            Domoticz.Debug("Current Inverter:" + str(self.currentInverter))
            Connection.Send({
                "Verb": "GET",
                "URL": self.cmds[self.currentInverter],
                "Headers": headers
		    })
		    
    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("Status:" + str(Status))
        self.sendData(Connection)
	

    def onMessage(self, Connection, Data):
        Domoticz.Debug("Data:" + str(Data))
        if Data and "Data" in Data:
            Domoticz.Debug("Current Inverter:" + str(self.currentInverter))
            cur = self.currentInverter
            
            dJson = json.loads(Data["Data"].decode())
            self.currents[cur] = int(dJson["result"][SOLAX_CURRENT])
            self.cumuls[cur] = int(float(dJson["result"][SOLAX_SUM])*1000)
            
            if(cur+1 < len(self.invertersSN)):

                self.currentInverter += 1
                Domoticz.Debug("Load next inverter:" + str(self.currentInverter))
                self.getData(self.currentInverter)
            else: 
                #Connection.Disconnect()
                self.currentInverter = 0
                self.updateDevices()

    def onDisconnect(self, Connection):
        Domoticz.Log("Device has disconnected")
        self.httpConn = None

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat called")
        currentTime = datetime.datetime.now().time()
    
        if currentTime > self.morning and currentTime < self.night:
            if self.heartbeat < self.beatcount:
                self.heartbeat = self.heartbeat + 1
                Domoticz.Debug("hearbeat:" + str(self.heartbeat))
            else:
                self.getData()
                self.heartbeat = 0
#        else:
#            Domoticz.Debug("Night time, no data")

    def updateDevices(self):

        Domoticz.Debug("updateDevices called")
        nbInverters = len(self.invertersSN)
        Domoticz.Debug("nbInverters : " + str(nbInverters))
        if nbInverters > 1:

            self.currents[nbInverters] = 0
            self.cumuls[nbInverters] = 0


            for i,d in enumerate(self.invertersSN):
                
                self.cumuls[nbInverters]+=self.cumuls[i]
                Domoticz.Debug("self.cumuls[" + str(i) + "]= " + str(self.cumuls[i]) )
                Domoticz.Debug("self.cumuls[" + str(nbInverters) + "]= " + str(self.cumuls[nbInverters]) )
                self.currents[nbInverters]+=self.currents[i]
                Domoticz.Debug("self.currents[" + str(i) + "]= " + str(self.currents[i]) )
                Domoticz.Debug("self.currents[" + str(nbInverters) + "]= " + str(self.currents[nbInverters]) )

        for i,d in enumerate(Devices):
            self.updateDevice(i+1)

    def updateDevice(self, Unit):
        Domoticz.Debug("updateDevice called " + str(Unit))
        # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
        if (Unit in Devices):
            strValue =  str(self.currents[Unit-1]) + ";" + str(self.cumuls[Unit-1])
            Domoticz.Debug("strValue :" + strValue)
            if(Devices[Unit].sValue != strValue):
                Devices[Unit].Update(nValue=0, sValue=strValue)
                Domoticz.Log("Update 0:'"+ strValue +"' ("+Devices[Unit].Name+")")
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
