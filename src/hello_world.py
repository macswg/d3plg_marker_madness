__all__ = ["addTextLayer"]

def addTextLayer():
      layer = guisystem.track.addNewLayer(TextModule, LocalState.localState().currentTransport.player.tCurrent, 60, 'Text')
      layer.findSequence('text').sequence.setString(0, "Hello world")
      return True
      """
      Set the playhead position to the specified time in seconds.
      Uses forceJump method on the transport to jump to the specified time.
      Python 2.7 compatible.
      """
      timeValue = float(time)
      transport = LocalState.localState().currentTransport
      transportManager = guisystem.currentTransportManager
      
      # Try different approaches to set the playhead
      # Method 1: Try forceJump with just time (most likely)
      try:
          transport.forceJump(timeValue)
          print("Set playhead to " + str(timeValue) + " seconds using forceJump")
          return True
      except:
          pass
      
      # Method 2: Try forceJump with time as integer (maybe it needs frames?)
      try:
          # Convert to frames (assuming 30 fps)
          frames = int(timeValue * 30)
          transport.forceJump(frames)
          print("Set playhead to " + str(timeValue) + " seconds (" + str(frames) + " frames) using forceJump")
          return True
      except:
          pass
      
      # Method 3: Try forceJump with transport name first, then time
      try:
          transport.forceJump('default', timeValue)
          print("Set playhead to " + str(timeValue) + " seconds using forceJump with name")
          return True
      except:
          pass
      
      # Method 4: Try forceJump with time first, then transport name
      try:
          transport.forceJump(timeValue, 'default')
          print("Set playhead to " + str(timeValue) + " seconds using forceJump with time first")
          return True
      except:
          pass
      
      # Method 3: Try using transport manager's forceJump
      try:
          transportManager.forceJump('default', timeValue)
          print("Set playhead to " + str(timeValue) + " seconds using transportManager.forceJump")
          return True
      except:
          pass
      
      # Method 4: Try setting tCurrent directly (might work in some cases)
      try:
          transport.player.tCurrent = timeValue
          print("Set playhead to " + str(timeValue) + " seconds using tCurrent")
          return True
      except:
          pass
      
      # Method 5: Try using the transport's timecode property
      try:
          # Convert seconds to timecode format (HH:MM:SS:FF)
          hours = int(timeValue / 3600)
          minutes = int((timeValue % 3600) / 60)
          seconds = int(timeValue % 60)
          frames = int((timeValue % 1) * 30)  # Assuming 30 fps
          timecodeStr = "%02d:%02d:%02d:%02d" % (hours, minutes, seconds, frames)
          transport.timecode = timecodeStr
          print("Set playhead to " + str(timeValue) + " seconds using timecode: " + timecodeStr)
          return True
      except:
          pass
      
      # Method 6: Try using sendTransportCommands
      try:
          # Try sending a command to jump to the time
          transport.sendTransportCommands('jump', timeValue)
          print("Set playhead to " + str(timeValue) + " seconds using sendTransportCommands")
          return True
      except:
          pass
      
      # Method 7: Try accessing through the transport manager's current property
      try:
          transportManager.current = timeValue
          print("Set playhead to " + str(timeValue) + " seconds using transportManager.current")
          return True
      except:
          pass
      
      # Method 8: Try calling forceJump through the transport manager with transport object
      try:
          defaultTransport = transportManager.getTransport('default')
          # Try calling forceJump on the manager with transport and time
          if hasattr(transportManager, 'forceJump'):
              transportManager.forceJump(defaultTransport, timeValue)
              print("Set playhead to " + str(timeValue) + " seconds using transportManager.forceJump with transport")
              return True
      except:
          pass
      
      # Method 9: Try stopping, setting time, then the transport might allow it
      try:
          wasPlaying = transport.player.playing
          if wasPlaying:
              transport.player.Stop()
          # Try setting tCurrent after stopping
          transport.player.tCurrent = timeValue
          if wasPlaying:
              transport.player.Play()
          print("Set playhead to " + str(timeValue) + " seconds (stopped, set, resumed)")
          return True
      except:
          pass
      
      # Method 10: Try using the transport's beatToTimecode and then setting
      try:
          # Maybe we need to convert to timecode first
          timecode = transport.beatToTimecode(timeValue)
          transport.timecode = timecode
          print("Set playhead to " + str(timeValue) + " seconds using beatToTimecode")
          return True
      except:
          pass
      
      # Method 10: Debug - print what forceJump actually expects
      try:
          # Try to see if forceJump is callable and what it expects
          if callable(transport.forceJump):
              # Try with just time as float
              result = transport.forceJump(timeValue)
              print("forceJump returned: " + str(result))
              return True
      except:
          print("forceJump callable but failed")
      
      print("Error: All methods to set playhead failed. Time value: " + str(timeValue))
      return False
