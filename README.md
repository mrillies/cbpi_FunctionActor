# cbpi_FunctionActor
A CraftBeerPi Actor that adds functions to any basic actor.
Please contact me here or at mrillies87@gmail.com if you need help writing rules

## Base Paramters
### Slave Actor: 
- Actor to be controlled. 
    - Once an actor has been asigned as a slave it should be hidden and not allocated directly to a kettle/feremntor/other actor
    - Status of slave actor output can be seen in the power percentage value of the fucntion actor

### Time Parameters
- On Delay: How many seconds to wait before turning on
- Off Delay: How many seconds to wait before turning off
- Cycle Delay: Minimum time after turn off before actor can turn on again (eg compressor protection)

## Trigger
- Trigger Sensor: Sensor to base trigger on 
- Trigger Rule: sensor, on and off are keywords
    - Use 'i' before and/or after the rule to ignore delay times

### Trigger Rule Examples
- (sensor > 20) : when sensor rises above 20, delay on counter starts, when it falls below, delay off counter starts
- i(sensor > 20) : delay on counter starts at 'on' command, trigger must still be above 20 for it to turn on
- (sensor > 20)i : when sensor rises above 20, delay on counter starts, when it falls below, actor switches off immediately
- (off and (sensor > 20)) or (on and (sensor > 10)) : when off, turn on above 20. When on, stay on while above 20 (hysterisis)

## Contol Func
Provides extended functionality that can be added to in future edits

### Currently supported commands
- On pulse series: P followed by a list. Starts after delay on 
    - Example P(1,1,1) Start On, 1sec then off, 1sec then on, 1 sec then off. Odd numbers of params stay off, even stay on
- Off pulse series: p followed by list. Starts after delay off or imediate if imediate trigger.
    - Example p(1,1,1) Start Off, 1sec then on, 1sec then off, 1 sec then on, then off. Odd numbers of params will have a short end pulse


A background task forces the slave actor every 0.2 seconds to minimise glitches from accidental switching
Only set trigger and control params if needed to minimise amount of code executed

