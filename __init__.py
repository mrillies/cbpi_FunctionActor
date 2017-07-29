from modules import cbpi
from modules.core.props import Property
from modules.core.hardware import ActorBase, SensorPassive, SensorActive
from datetime import datetime, timedelta

function_actor_ids = []

''' 
Function Actor 

Contains the following

actor_execute:
Backgorund task to call execute_func on Function Actors

tryfloat:
number validator for properties, returns 0 as default


FunctionActor:
    init:
    Adds actor to execute list and validates properites
    
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

@cbpi.backgroundtask(key="actor_execute", interval=.5)
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
                cbpi.notify("Actor Error", "Failed to execute actor %s. Please update the configuraiton" % actor.name, type="danger", timeout=0)
                cbpi.app.logger.error("Execute of Actor %s failed, removed from execute list" % id)  
                function_actor_ids.remove(id)
                print e
 
# returns zero if num is not a number 
def tryfloat(num):
    try:
        out = float(num)
    except:
        out = float(0)
    return out

def tryint(num):
    try:
        out = int(num)
    except:
        out = int(0)
    return out
                        
            
@cbpi.actor
class FunctionActor(ActorBase):
    global function_actor_ids
    
    #Properties
    on_delay = Property.Number("On Delay", configurable = True, default_value=0, description = "On wait time in seconds")
    off_delay = Property.Number("Off Delay", configurable = True, default_value=0, description = "Off wait time in seconds")
    cycle_delay = Property.Number("Cycle Delay", configurable = True, default_value=0, description = "Minimum time before next turn on in seconds")
    max_on = Property.Number("Max On Time", configurable = True, default_value=0, description = "NOT READY: Maximum actor on time, use 0.1 for single pulse, Zero to disable feature")
    output_actor = Property.Actor("Slave Actor", description="Select an Actor to be controlled")
    trigger_sensor = Property.Sensor("Trigger Input", description="Select a Sensor to be used as a trigger")
    trigger_type = Property.Select("Trigger Type", ["None","Equal","Above","Below"], description="Choose a trigger type")
    trigger_true_value = Property.Number("Trigger Value", configurable = True, default_value=0, description="Value when trigger is True" )
    
    #guards and stored vals
    on_delay_time = 0
    off_delay_time = 0
    cycle_delay_time = 0
    max_on_time = 0
    out_on = False      #output value
    out_req = False     #requested output value
    out_trig = False    #mux of out_req and trigger status
    last_trigger = False    #result of last trigger check
    
    #output timers
    off_time = datetime.utcnow()    
    on_time = datetime.utcnow()
    cycle_wait = datetime.utcnow()

    power = 100
   
    def init(self):
        cbpi.app.logger.info("Func Actor init")
        if not int(self.id) in function_actor_ids:
            function_actor_ids.append(int(self.id))
        self.api.switch_actor_off(int(self.output_actor))
        self.on_delay_time = timedelta(seconds=tryfloat(self.on_delay))
        self.off_delay_time = timedelta(seconds=tryfloat(self.off_delay))
        self.cycle_delay_time = timedelta(seconds=tryfloat(self.cycle_delay))
        self.max_on_time = timedelta(seconds=tryfloat(self.max_on))
        self.trigger_true_val = tryfloat(self.trigger_true_value)
    
    def trigger_eval(self):
        if self.out_req == True:
            trigger_value = tryfloat(cbpi.get_sensor_value(tryint(self.trigger_sensor)))
            if self.trigger_type == "Equal":
                trig_sig = (int(trigger_value) == int(self.trigger_true_value))
            elif self.trigger_type == "Above":
                trig_sig = (float(trigger_value) >= float(self.trigger_true_value))
            elif self.trigger_type == "Below":
                trig_sig = (float(trigger_value) <= float(self.trigger_true_value))
            else:
                trig_sig = False
                
            if trig_sig == True:
                if self.last_trigger == False:
                    self.on_time = datetime.utcnow() + self.on_delay_time
                self.last_trigger = True
                return True
            else:
                if self.last_trigger == True:
                    self.off_time = datetime.utcnow() + self.off_delay_time
                self.last_trigger = False
                return False
                       
        else:
            return self.out_req
        return True
    	
    def execute_func(self):
        #evaluate trigger
        if isinstance(self.trigger_sensor, unicode) and self.trigger_sensor:
            self.out_trig = self.trigger_eval()
        else:
            self.out_trig = self.out_req
            
        #evalute output condition 
        if self.out_trig != self.out_on:
            right_now = datetime.utcnow()
            if (right_now >= self.on_time) and (right_now >= self.cycle_wait) and (self.out_trig == True):
                self.out_on = True
            if (right_now >= self.off_time) and (self.out_trig == False):
                if self.out_on:
                    self.cycle_wait = right_now + self.cycle_delay_time
                self.out_on = False
        
        #set output_actor and change func actor power displayed
        if cbpi.cache.get("actors").get(int(self.output_actor)).state != self.out_on:      
            if self.out_on == True:
                self.api.switch_actor_on(int(self.output_actor), power=self.power)
                self.display_power(self.power)
                
            else:
                self.api.switch_actor_off(int(self.output_actor))
                self.display_power(0)
        if self.out_on == False:
            self.display_power(0)


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
