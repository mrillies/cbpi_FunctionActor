from modules import cbpi
from modules.core.props import Property
from modules.core.hardware import ActorBase, SensorPassive, SensorActive
from datetime import datetime, timedelta

function_actor_ids = []

''' 
Function Actor

actor_execute:
Backgorund task to call execute_func on Function Actors

tryfloat/tryint:
number validator for properties, can return a default


FunctionActor:
    init:
    Adds actor to execute list and validates properites
    
    decode_control_word:
    identify advanced commands in function control word
    
    trigger_eval:
    checks if trigger condition is satisfied
    
    execute_func:
    function executed by the background task
    
    on/off/setpower:
    sets flags and timmers for execute function
    
    display_power:
    changes actors diplayed power without changing slave actor actual power
    used to show if slave actor is on or off.
    
'''

@cbpi.backgroundtask(key="actor_execute", interval=.2)
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
                print e
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
    b_on_delay = Property.Number("On Delay", configurable = True, default_value=0, description = "On wait time in seconds")
    c_off_delay = Property.Number("Off Delay", configurable = True, default_value=0, description = "Off wait time in seconds")
    d_cycle_delay = Property.Number("Cycle Delay", configurable = True, default_value=0, description = "Minimum time before next turn on in seconds")
    h_control_word = Property.Text("Control Func", configurable = True, default_value="", description = "Control function executed when actor switches on, see Readme for more info")
    a_output_actor = Property.Actor("Slave Actor", description="Select an Actor to be controlled")
    f_trigger_sensor = Property.Sensor("Trigger Sensor", description="Select a Sensor to be used as a trigger")
    g_trigger_text = Property.Text("Trigger Rule", configurable = True, default_value="True", description="Trigger eqation, use sensor as key word, eg sensor > 25" )

    def init(self):
        try:
            cbpi.app.logger.info("Func Actor init")
            
            #guards and stored vals
            self.out_on = False      #slave actor output value 
            self.out_active = False  #actor state
            self.out_req = False     #ui requested actor state
            self.out_trig = False    #mux of out_req and trigger
            self.power = 100
            
            #function vars
            self.on_pulse_list = []
            self.off_pulse_list = []
            self.on_pulses = []
            self.off_pulses = []
            self.last_trigger = False    #result of last trigger check
            self.trig_immediate_on = False
            self.trig_immediate_off = False

            #output timers
            self.off_time = datetime.utcnow()    
            self.on_time = datetime.utcnow()
            self.cycle_wait = datetime.utcnow()
            self.func_time = datetime.utcnow()
            self.on_delay_time = timedelta(seconds=tryfloat(self.b_on_delay))
            self.off_delay_time = timedelta(seconds=tryfloat(self.c_off_delay))
            self.cycle_delay_time = timedelta(seconds=tryfloat(self.d_cycle_delay))

            #remove 'ordering' letter
            self.control_word = self.h_control_word
            self.output_actor = self.a_output_actor
            self.trigger_sensor = self.f_trigger_sensor
            self.trigger_text = self.g_trigger_text

            #check for sensor and trigger config 
            if isinstance(self.trigger_sensor, unicode) and self.trigger_sensor and isinstance(self.trigger_text, unicode) and self.trigger_text:           
                if self.trigger_text[0] == "I" or self.trigger_text[0] == "i":
                    self.trig_immediate_on = True
                    self.trigger_text = self.trigger_text[1:]
                if self.trigger_text[-1] == "I" or self.trigger_text[-1] == "i":
                    self.trig_immediate_off = True
                    self.trigger_text = self.trigger_text[:-1] 
            else:
                self.trigger_sensor = None
                self.trigger_text = None

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
            print e
            print e.__class__.__name__
            e.throw
    
    def decode_control_word(self):
        try:
            word_temp = self.control_word.replace("_","")
            word_temp = word_temp.replace("(","[")
            word_temp = word_temp.replace(")","]")
            words_temp = word_temp.split()
            for word in words_temp:
                if word[0] == "P":   #Pulse command
                    print "On Pulse command"
                    self.on_pulse_list = tuple(eval(word[1:]))
                elif word[0] == "p":   #Pulse command
                    print "Off Pulse command"
                    self.off_pulse_list = tuple(eval(word[1:]))
                elif word[0] == "R":   #Ramp command
                    print "On Ramp command"
                elif word[0] == "r":   #Ramp command
                    print "Off Ramp command"
                else:
                    raise ValueError("Control char not recognised")
        except Exception as e:
            print "Control Word not valid"
            print e
            cbpi.app.logger.error("Control Word not valid")
            return False            
        return True
    
    def trigger_eval(self):
        #print "trigger"
        if self.out_req == True:
            sensor = tryfloat(cbpi.get_sensor_value(tryint(self.trigger_sensor)))
            on = self.out_active
            off = not self.out_active
            trig_sig = bool(eval(self.trigger_text))
            #print trig_sig

            #based on trigger and immediate settings, enable or disable actor            
            if trig_sig == True:
                if self.last_trigger == False and not self.trig_immediate_on:
                    self.on_time = datetime.utcnow() + self.on_delay_time
                self.last_trigger = True
                return True
            else:
                if self.last_trigger == True and not self.trig_immediate_off:
                    self.off_time = datetime.utcnow() + self.off_delay_time
                self.last_trigger = False
                return False
                       
        else:
            return self.out_req
        #should not get here
        print "Trigger code Failure: should not be here"
        return False
    	
    def execute_func(self):

        #evaluate trigger if setup was valid
        if self.trigger_sensor and self.trigger_text:
            self.out_trig = self.trigger_eval()
        else:
            self.out_trig = self.out_req   

        #evalute active condition
        right_now = datetime.utcnow()
        if self.out_trig != self.out_active:
            if self.out_active:
                if (self.out_trig == False) and (right_now >= self.off_time):
                    self.out_active = False
                    self.out_on = False
                    self.func_time = right_now
                    self.off_pulses = list(self.off_pulse_list)
                    self.cycle_wait = right_now + self.cycle_delay_time
            else:
                if (self.out_trig == True) and (right_now >= self.on_time) and (right_now >= self.cycle_wait):
                    self.out_active = True
                    self.out_on = True
                    self.func_time = right_now
                    self.on_pulses = list(self.on_pulse_list)
                    
        #set output_actor and change func actor power displayed
        if cbpi.cache.get("actors").get(int(self.output_actor)).state != self.out_on:      
            if self.out_on == True:
                self.api.switch_actor_on(int(self.output_actor), power=self.power)
                self.display_power(self.power)   
            else:
                self.api.switch_actor_off(int(self.output_actor))
                self.display_power(0)
        
        # overwrite displayed power as Zero if slave actor is off        
        if self.out_on == False and cbpi.cache.get("actors").get(int(self.id)).power != 0:
            self.display_power(0)
     
        #evalute output pulsing
        if self.out_active:
            if len(self.on_pulses) > 0:
                if right_now > self.func_time + timedelta(seconds=tryfloat(self.on_pulses[0])):
                    self.out_on = not self.out_on
                    del self.on_pulses[0]
                    self.func_time = right_now
        else:
            if len(self.off_pulses) > 0:
                if right_now > self.func_time + timedelta(seconds=tryfloat(self.off_pulses[0])):
                    self.out_on = not self.out_on
                    del self.off_pulses[0]
                    self.func_time = right_now
            else:
                self.out_on = False

    def on(self, power=None):
        if power is not None:
            self.power = power

        if self.out_req == False:
            self.out_req = True
            self.on_time = datetime.utcnow() + self.on_delay_time
               
    
    def off(self):
        if self.out_req == True:            
            self.out_req = False            
            self.off_time = datetime.utcnow() + self.off_delay_time
        

    def set_power(self, power = None):
        if power is not None:
            self.power = power
        self.api.actor_power(int(self.output_actor), power=self.power)


    def display_power(self, pwr):
        actor = cbpi.cache.get("actors").get(int(self.id))
        actor.power = pwr
        cbpi.emit("SWITCH_ACTOR", actor)
