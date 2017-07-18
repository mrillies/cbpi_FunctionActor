# cbpi_FunctionActor
An CraftBeerPi Actor that adds functions to any basic actor.

Currently supports delays:
- On Delay - How many seconds to wait before turning on
- Off Delay - How many seconds to wait before turning off
- Cycle Delay - Minimum time after turn off before actor can turn on again (eg compressor protection)

Triggers in development:
- Settings are visible in dashboard but are not connected

A background task forces the slave actor every 0.1 seconds to minimise glitches from accidental switching
