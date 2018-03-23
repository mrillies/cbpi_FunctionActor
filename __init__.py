from modules import cbpi
from modules.core.props import Property
from modules.core.hardware import ActorBase, SensorPassive, SensorActive
from datetime import datetime, timedelta
import traceback

function_actor_ids = []


@cbpi.backgroundtask(key="actor_execute", interval=.1)
def actor_execute(api):
    global function_actor_ids
    for id in function_actor_ids:
        actor = cbpi.cache.get("actors").get(id)
        #test for deleted Func actor
        if actor is None:
            function_actor_ids.remove(id)
        else:
            try:    # try to call execute. Remove if execute fails. Added back when settings updated
                actor.instance.execute_func()
            except Exception as e:
                traceback.print_exc()
                cbpi.notify("Actor Error", "Failed to execute actor %s. Please update the configuraiton" % actor.name, type="danger", timeout=0)
                cbpi.app.logger.error("Execute of Actor %s failed, removed from execute list" % id)  
                function_actor_ids.remove(id)
                
 
# returns zero if num is not a number 
def tryfloat(num, def_ret=0):
    try:
        out = float(num)
    except:
        if def_ret is None:
            out = None
        else:
            out = float(def_ret)
        print "float fail"
    return out


def tryint(num, def_ret=0):
    try:
        out = int(num)
    except:
        if def_ret is None:
            out = None
        else:
            out = int(def_ret)
        print "int fail"
    return out
                        
            
@cbpi.actor
class FunctionActor(ActorBase):
    global function_actor_ids
    
    #Properties
    a_output_actor = Property.Actor("Slave Actor", description="Select an Actor to be controlled")
    b_on_delay = Property.Number("On Delay", configurable = True, default_value=0, description = "On wait time in seconds")
    c_off_delay = Property.Number("Off Delay", configurable = True, default_value=0, description = "Off wait time in seconds")
    d_cycle_delay = Property.Number("Cycle Delay", configurable = True, default_value=0, description = "Minimum time before next turn on in seconds")
    h_control_word = Property.Text("Control Func", configurable = True, default_value="", description = "Control function executed when actor switches on, see Readme for more info")
    
    trigger_sensor_a = Property.Sensor("Trigger Sensor 1 (S1 or sensor)", description="Select a Sensor to be used as a trigger")
    trigger_sensor_b = Property.Sensor("Trigger Sensor 2 (S2)", description="Select a Sensor to be used as a trigger")
    trigger_text = Property.Text("Trigger Rule", configurable = True, default_value="True", description="Trigger eqation, use sensor as key word, eg sensor > 25" )

    def init(self):
        try:
            cbpi.app.logger.info("Func Actor init")
            
            #guards and stored vals
            self.out = dict.fromkeys(["on","req","active", "im_on", "im_off", "no_force", "last_on"], False)    #on: slave state, active: actor state trig: actor is triggered req: slave on is requested
            self.power = 100

            #output timers
            time_now = datetime.utcnow()
            self.times = dict.fromkeys(["onoff","cycle"], time_now)
            self.delay = {}
            self.delay["on"] = timedelta(seconds=tryfloat(self.b_on_delay))
            self.delay["off"] = timedelta(seconds=tryfloat(self.c_off_delay))
            self.delay["cycle"] = timedelta(seconds=tryfloat(self.d_cycle_delay))

            self.pulse = {"on_list":[], "off_list":[], "next":[], "loop": False}

            #remove 'ordering' letter
            self.control_word = self.h_control_word
            self.output_actor = self.a_output_actor
            

            #check for sensor and trigger config 
            if (((isinstance(self.trigger_sensor_a, unicode) and self.trigger_sensor_a) 
                or (isinstance(self.trigger_sensor_b, unicode) and self.trigger_sensor_b)) 
                and isinstance(self.trigger_text, unicode) and self.trigger_text):
                
                self.trig = {"s1":None, "s2": None, "text": self.trigger_text}
                if isinstance(self.trigger_sensor_a, unicode) and self.trigger_sensor_a:
                     self.trig["s1"] = self.trigger_sensor_a
                if isinstance(self.trigger_sensor_b, unicode) and self.trigger_sensor_b:
                     self.trig["s2"] = self.trigger_sensor_b         
                
                self.trig.update(dict.fromkeys(["last", "im_on", "im_off", "type"], False))
            else:
                self.trig = None
                
            #check for control word config
            if isinstance(self.control_word, unicode) and self.control_word:
                self.control_word = self.decode_control_word()
            else:
                self.control_word = None         

            #add actor to list to execute
            if not int(self.id) in function_actor_ids:
                function_actor_ids.append(int(self.id))
            self.api.switch_actor_off(int(self.output_actor))
            self.display_power(0)
            
        except Exception as e:
            print "Function init fail"
            traceback.print_exc()
            e.throw
    
    def decode_control_word(self):
        
        try:
            #pulse vars
                      
            word_temp = self.control_word.replace("_","")
            word_temp = word_temp.replace("(","[")
            word_temp = word_temp.replace(")","]")
            words_temp = word_temp.split()
            
            for word in words_temp:    
                if word[0] == "P":   #Pulse command
                    print "On Pulse command"
                    self.pulse["on_list"] = tuple(eval(word[1:]))
                    self.pulse["loop"] = False
                elif word[0] == "p":   #Pulse command
                    print "Off Pulse command"
                    self.pulse["off_list"] = tuple(eval(word[1:]))
                elif word[0] == "L":   #Pulse command
                    print "Loop command"
                    self.pulse["on_list"] = tuple(eval(word[1:]))
                    self.pulse["loop"] = True
                elif word[0] == "R":   #Ramp command
                    print "On Ramp command not implemented"
                elif word[0] == "r":   #Ramp command
                    print "Off Ramp command not implemented"
                elif word == "trigSwitchActor":
                    self.trig["type"] = "Sw"
                elif word == "trigToggleActor":
                    self.trig["type"] = "Tog"
                elif word == "trigImOn":
                    self.trig["im_on"] = True
                elif word == "trigImOff":
                    self.trig["im_off"] = True
                elif word == "UiImOn":
                    self.out["im_on"] = True
                elif word == "UiImOff":
                    self.out["im_off"] = True
                elif word == "noForce":
                    self.out["no_force"] = True
                else:
                    print word
                    raise ValueError("Control word not valid")
        except Exception as e:
            print e
            cbpi.app.logger.error("Control Word not valid")
            return False            
        return True
    
    def trigger_eval(self):
        #print "trigger"
        if self.trig["s1"]:
            sensor = tryfloat(cbpi.get_sensor_value(tryint(self.trig["s1"])))
        else:
            sensor = 0
        s1 = sensor
        if self.trig["s2"]:
            s2 = tryfloat(cbpi.get_sensor_value(tryint(self.trig["s2"])))
        else:
            s2 = 0
        on = self.out["active"]
        state = self.out["on"]
        off = not self.out["active"]
        trig_sig = bool(eval(self.trig["text"]))
            
        #based on trigger and immediate settings, enable or disable actor            
        if trig_sig == True:
            if self.trig["last"] is False:
                if self.trig["type"] == "Tog":
                    pass #toggle actor
                    self.update_self(self.power, "Tog")
                elif self.trig["type"] == "Sw":
                    pass # switch actor on
                    self.update_self(self.power, True)
                if not self.trig["im_on"]:
                    self.times["onoff"] = datetime.utcnow() + self.delay["on"]
                self.trig["last"] = True
            return self.out["req"]
        else:
            if self.trig["last"] is True:
                if self.trig["type"] == "NTog":
                    pass #toggle actor on negative switch
                elif self.trig["type"] == "Sw":
                    pass # switch actor off
                    self.update_self(self.power, False)
                if not self.trig["im_off"]:
                    self.times["onoff"] = datetime.utcnow() + self.delay["off"]
                self.trig["last"] = False
            if self.trig["type"] is False:
                return False
            else:
                return self.out["req"]

                       
        #should not get here
        print "Failure: should not be here"
        return False
    	
    def execute_func(self):
        
        #evaluate trigger if setup was valid
        if self.trig is not None:
            trigger = self.trigger_eval()
        else:
            trigger = self.out["req"]   
        
        #evalute active condition
        right_now = datetime.utcnow()
        if trigger != self.out["active"]:
            if (right_now >= self.times["onoff"]) and ((right_now >= self.times["cycle"]) or not trigger):
                self.out["active"] = trigger
                self.out["on"] = trigger
                if trigger:
                    self.pulse["next"] = list(self.pulse["on_list"])
                else:
                    self.pulse["next"] = list(self.pulse["off_list"])
                if len(self.pulse["next"]) > 0:
                    self.times["pulse"] = right_now + timedelta(seconds=tryfloat(self.pulse["next"][0]))
                       
        #set output_actor and change func actor power displayed
        if ((cbpi.cache.get("actors").get(int(self.output_actor)).state != self.out["on"]) or (self.out["no_force"] == True)):
            if ((self.out["no_force"] == False) or (self.out["on"] != self.out["last_on"])):
                self.out["last_on"] = self.out["on"]
                if self.out["on"] == True:
                    self.api.switch_actor_on(int(self.output_actor), power=self.power)
                    self.display_power(self.power)   
                else:
                    self.api.switch_actor_off(int(self.output_actor))
                    self.display_power(0)
        
        # overwrite displayed power as Zero if slave actor is off        
        if self.out["on"] == False and cbpi.cache.get("actors").get(int(self.id)).power != 0:
            self.display_power(0)
     
        #evalute output pulsing
        if len(self.pulse["next"]) > 0:
            if right_now > self.times["pulse"]:
                self.out["on"] = not self.out["on"]
                del self.pulse["next"][0]
                if len(self.pulse["next"]) == 0:
                    if self.pulse["loop"] and self.out["active"]:
                        self.pulse["next"] = list(self.pulse["on_list"])
                if len(self.pulse["next"]) > 0:
                    self.times["pulse"] = right_now + timedelta(seconds=tryfloat(self.pulse["next"][0]))
         
        else:
            if not self.out["active"]:
                self.out["on"] = False
                if self.out["last_on"]:
                    self.times["cycle"] = right_now + self.delay["cycle"]

                

    def on(self, power=None):
        if power is not None:
            self.power = power

        if self.out["req"] is False:
            self.out["req"] = True
            if self.out["im_on"] is False:
                self.times["onoff"] = datetime.utcnow() + self.delay["on"]
               
    
    def off(self):
        if self.out["req"] == True:            
            self.out["req"] = False
            if self.out["im_off"] is False:           
                self.times["onoff"] = datetime.utcnow() + self.delay["off"]
        

    def set_power(self, power = None):
        if power is not None:
            self.power = power
        self.api.actor_power(int(self.output_actor), power=self.power)

    def update_self(self, pwr, state):
        actor = cbpi.cache.get("actors").get(int(self.id))
        actor.power = pwr
        if state == "Tog":
            state = not actor.state
        if actor.state != state:
            actor.state = state
            self.out["req"] = state
            cbpi.emit("SWITCH_ACTOR", actor)    

    def display_power(self, pwr):
        actor = cbpi.cache.get("actors").get(int(self.id))
        actor.power = pwr
        cbpi.emit("SWITCH_ACTOR", actor)
