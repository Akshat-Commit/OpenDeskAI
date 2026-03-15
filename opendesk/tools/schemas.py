from pydantic import BaseModel, Field # type: ignore
from typing import Optional

class TypeTextInput(BaseModel):
    text: str = Field(description="The exact text string to type on the keyboard.")
    press_enter: bool = Field(default=False, description="Set this to true if you want to automatically press the Enter key immediately after typing the text (e.g., to submit a form or send a message).")

class RunTerminalCommandInput(BaseModel):
    command: str = Field(description="The exact terminal/powershell command to run on the Windows host. E.g., 'dir', 'echo hello'.")

class ClickMouseInput(BaseModel):
    x: Optional[int] = Field(default=None, description="The X coordinate on the screen to click on.")
    y: Optional[int] = Field(default=None, description="The Y coordinate on the screen to click on.")
    button: str = Field(default="left", description="The mouse button to click. Must be 'left', 'right', or 'middle'.")
    clicks: int = Field(default=1, description="The number of times to click. Use 1 for single click, 2 for double click.")

class CaptureVideoInput(BaseModel):
    duration: int = Field(default=5, description="The duration of the video to record, in seconds. Minimum 1, maximum 60.")
    save_path: Optional[str] = Field(default=None, description="Optional relative or absolute file path to save the .mp4 file. If none is provided, a default timestamped filename will be used.")

class CaptureWebcamInput(BaseModel):
    save_path: Optional[str] = Field(default=None, description="Optional relative or absolute file path to save the .jpg photo. If none is provided, a default timestamped filename will be used.")

class TakeScreenshotInput(BaseModel):
    save_path: Optional[str] = Field(default=None, description="Optional relative or absolute file path to save the .png screenshot. If none is provided, a default timestamped filename will be used.")

class OpenAppInput(BaseModel):
    app_name: str = Field(description="The common name of the application you want to open. For example: 'vscode', 'chrome', 'whatsapp', 'calculator', 'notepad'.")

class CloseAppInput(BaseModel):
    app_name: str = Field(description="The name of the application you want to close.")

class PressKeyInput(BaseModel):
    key: str = Field(description="The exact key you want to press. Examples: 'enter', 'win', 'space', 'tab', 'esc', 'ctrl', 'shift'.")

class SendWhatsappMessageInput(BaseModel):
    contact_name: str = Field(description="The exact name of the person or group you want to message, as saved in WhatsApp.")
    message: str = Field(description="The text message you want to send.")

class PlaySpotifyMusicInput(BaseModel):
    song_name: str = Field(description="The exact name of the song, artist, or album you want to play.")

class ControlMediaInput(BaseModel):
    action: str = Field(description="The media control action to perform. Must be one of: 'playpause', 'next', 'previous', 'mute'. Do NOT use this for volume control.")

class SetVolumeInput(BaseModel):
    level: int = Field(description="The exact volume percentage to set the system audio to. Must be an integer between 0 and 100.")


class GetRunningProcessesInput(BaseModel):
    name_filter: Optional[str] = Field(default=None, description="Optional substring to filter processes by name (e.g., 'chrome', 'python'). If omitted, returns top 20 processes by memory.")

class TerminateProcessInput(BaseModel):
    pid: int = Field(description="The exact Process ID (PID) to gracefully terminate.")

class RunPythonScriptInput(BaseModel):
    code: str = Field(description="The exact, valid Python code string to be executed dynamically.")

class ShareFileInput(BaseModel):
    filename: str = Field(description="The name of the file to share (e.g., 'ak.jpg').")
    search_dir: Optional[str] = Field(default=None, description="Optional directory name to search in (e.g., 'Downloads', 'Documents').")

from typing import List

class CreateWordDocInput(BaseModel):
    content: str = Field(description="The main text content to write into the Word document.")
    filepath: Optional[str] = Field(default=None, description="Optional save path.")

class CreateExcelFileInput(BaseModel):
    sheet_name: str = Field(default="Sheet1", description="Name of the Excel sheet.")
    headers: Optional[List[str]] = Field(default=None, description="A list of string headers for the columns.")
    rows: Optional[List[List[str]]] = Field(default=None, description="A list of rows, where each row is a list of string values.")
    filepath: Optional[str] = Field(default=None, description="Optional save path.")

class CreatePowerPointInput(BaseModel):
    title: str = Field(description="The main title for the presentation.")
    subtitle: str = Field(description="The subtitle for the presentation.")
    bullets: Optional[List[str]] = Field(default=None, description="A list of string bullet points to add to the second slide.")
    filepath: Optional[str] = Field(default=None, description="Optional save path.")

# Mapping of tool names to their strict Pydantic Schemas
# Any tool not in this dictionary will use LangChain's default argument inference.
TOOL_SCHEMAS = {
    "type_text": TypeTextInput,
    "run_terminal_command": RunTerminalCommandInput,
    "click_mouse": ClickMouseInput,
    "capture_video": CaptureVideoInput,
    "capture_webcam": CaptureWebcamInput,
    "take_screenshot": TakeScreenshotInput,
    "open_app": OpenAppInput,
    "close_app": CloseAppInput,
    "press_key": PressKeyInput,
    "send_whatsapp_message": SendWhatsappMessageInput,
    "play_spotify_music": PlaySpotifyMusicInput,
    "control_media": ControlMediaInput,
    "set_volume": SetVolumeInput,
    "get_running_processes": GetRunningProcessesInput,
    "terminate_process": TerminateProcessInput,
    "run_python_script": RunPythonScriptInput,
    "share_file": ShareFileInput,
    "create_word_doc": CreateWordDocInput,
    "create_excel_file": CreateExcelFileInput,
    "create_powerpoint": CreatePowerPointInput,
}
