import sys
sys.path.append(r"c:\Users\AKSHAT JAIN\OneDrive\Desktop\OpenDeskAI")

def set_volume_test(level: int):
    from pycaw.pycaw import AudioUtilities
    devices = AudioUtilities.GetSpeakers()
    volume = devices.EndpointVolume
    
    scalar_vol = float(level) / 100.0
    if volume.GetMute():
        volume.SetMute(0, None)
    volume.SetMasterVolumeLevelScalar(scalar_vol, None)
    return f"Successfully set system volume to {level}%."

print(set_volume_test(50))
