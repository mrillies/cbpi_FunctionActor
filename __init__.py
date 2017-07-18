from modules import cbpi
from modules.core.props import Property
from modules.core.hardware import ActorBase, SensorPassive, SensorActive
from datetime import datetime, timedelta

function_actor_ids = []

@cbpi.backgroundtask(key="actor_execute", interval=0.1)
def actor_execute(api):
    global function_actor_ids
    #cbpi.app.logger.info("Actor Ex")    
    for id in function_actor_ids:
        #cbpi.app.logger.info("Actor Execute")
        actor = cbpi.cache.get("actors").get(id)
        actor.instance.execute()

@cbpi.actor
class FunctionActor(ActorBase):
    global function_actor_ids
    on_delay = Property.Number("On Delay", configurable = True, description = "On wait time in seconds")
    off_delay = Property.Number("Off Delay", configurable = True, description = "Off wait time in seconds")
    cycle_delay = Property.Number("Cycle Delay", configurable = True, description = "Minimum time before next turn on in seconds")
    output_actor = Property.Actor("Actor", description="Select an Actor to be controlled")
    trigger_sensor = Property.Sensor("Trigger Input", description="NOT DONE: Select a Sensor to be used as a trigger")
    trigger_type = Property.Select("Trigger Type", ["Equals","Above","Below"], description="NOT DONE: Choose a trigger type")
    trigger_value = Property.Number("Trigger Value", configurable = True, description="NOT DONE: Value to use for trigger, use zero/nonzero for false/true" )
    out_on = False
    out_trig = False
    off_time = datetime.utcnow()
    on_time = datetime.utcnow()
    cycle_wait = datetime.utcnow()
    power = 0
    

    def init(self):
        cbpi.app.logger.info("Func Actor init")
        function_actor_ids.append(int(self.id))    
    
    	
    def execute(self):
        if self.out_trig != self.out_on:
            right_now = datetime.utcnow()
            if (right_now >= self.on_time) and (right_now >= self.cycle_wait) and (self.out_trig == True):
                self.out_on = True
            if (right_now >= self.off_time) and (self.out_trig == False):
                if self.out_on:
                    self.cycle_wait = right_now + timedelta(seconds=int(self.cycle_delay))
                self.out_on = False
        if self.out_on == True:
            self.api.switch_actor_on(int(self.output_actor), power=self.power)
        else:
            self.api.switch_actor_off(int(self.output_actor))

    def on(self, power=0):
        self.power = power
        if self.out_trig == False:
            self.out_trig = True
            self.on_time = datetime.utcnow() + timedelta(seconds=int(self.on_delay))
               
    
    def off(self):
        if self.out_trig == True:            
            self.out_trig = False            
            self.off_time = datetime.utcnow() + timedelta(seconds=int(self.off_delay))
        
    def set_power(self, power=0):
        self.power = power

