# encoding: utf-8 -*- test-case-name:
# FIXME: Need to add tests.
# ipython1.frontend.cocoa.tests.test_cocoa_frontend -*-

"""Classes to provide a Wx frontend to the
IPython.kernel.core.interpreter.

"""

__docformat__ = "restructuredtext en"

#-------------------------------------------------------------------------------
#       Copyright (C) 2008  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Imports
#-------------------------------------------------------------------------------


import wx
import re
from wx import stc
from console_widget import ConsoleWidget
import __builtin__
from time import sleep

from IPython.frontend.prefilterfrontend import PrefilterFrontEnd

#_COMMAND_BG = '#FAFAF1' # Nice green
_RUNNING_BUFFER_BG = '#FDFFD3' # Nice yellow
_ERROR_BG = '#FFF1F1' # Nice red

_RUNNING_BUFFER_MARKER = 31
_ERROR_MARKER = 30

#-------------------------------------------------------------------------------
# Classes to implement the Wx frontend
#-------------------------------------------------------------------------------
class IPythonWxController(PrefilterFrontEnd, ConsoleWidget):

    output_prompt = \
    '\x01\x1b[0;31m\x02Out[\x01\x1b[1;31m\x02%i\x01\x1b[0;31m\x02]: \x01\x1b[0m\x02'
  
    #--------------------------------------------------------------------------
    # Public API
    #--------------------------------------------------------------------------
 
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=wx.CLIP_CHILDREN,
                 *args, **kwds):
        """ Create Shell instance.
        """
        ConsoleWidget.__init__(self, parent, id, pos, size, style)
        PrefilterFrontEnd.__init__(self)

        # Capture Character keys
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

        # Marker for running buffer.
        self.MarkerDefine(_RUNNING_BUFFER_MARKER, stc.STC_MARK_BACKGROUND,
                                background=_RUNNING_BUFFER_BG)
        # Marker for tracebacks.
        self.MarkerDefine(_ERROR_MARKER, stc.STC_MARK_BACKGROUND,
                                background=_ERROR_BG)



    def do_completion(self):
        """ Do code completion. 
        """
        line = self.get_current_edit_buffer()
        new_line, completions = self.complete(line)
        if len(completions)>1:
            self.write_completion(completions)
        self.replace_current_edit_buffer(new_line)


    def do_calltip(self):
        separators =  re.compile('[\s\{\}\[\]\(\)\= ,:]')
        symbol = self.get_current_edit_buffer()
        symbol_string = separators.split(symbol)[-1]
        base_symbol_string = symbol_string.split('.')[0]
        if base_symbol_string in self.shell.user_ns:
            symbol = self.shell.user_ns[base_symbol_string]
        elif base_symbol_string in self.shell.user_global_ns:
            symbol = self.shell.user_global_ns[base_symbol_string]
        elif base_symbol_string in __builtin__.__dict__:
            symbol = __builtin__.__dict__[base_symbol_string]
        else:
            return False
        for name in symbol_string.split('.')[1:] + ['__doc__']:
            symbol = getattr(symbol, name)
        try:
            self.AutoCompCancel()
            wx.Yield()
            self.CallTipShow(self.GetCurrentPos(), symbol)
        except:
            # The retrieve symbol couldn't be converted to a string
            pass


    def popup_completion(self, create=False):
        """ Updates the popup completion menu if it exists. If create is 
            true, open the menu.
        """
        line = self.get_current_edit_buffer()
        if (self.AutoCompActive() and not line[-1] == '.') \
                    or create==True:
            suggestion, completions = self.complete(line)
            offset=0
            if completions:
                complete_sep =  re.compile('[\s\{\}\[\]\(\)\= ,:]')
                residual = complete_sep.split(line)[-1]
                offset = len(residual)
                self.pop_completion(completions, offset=offset)


    def raw_input(self, prompt):
        """ A replacement from python's raw_input.
        """
        self.new_prompt(prompt)
        self.waiting = True
        self.__old_on_enter = self._on_enter
        def my_on_enter():
            self.waiting = False
        self._on_enter = my_on_enter
        # Busy waiting, ugly.
        while self.waiting:
            wx.Yield()
            sleep(0.1)
        self._on_enter = self.__old_on_enter
        return self.get_current_edit_buffer().rstrip('\n')
        
 
    def execute(self, python_string, raw_string=None):
        self.CallTipCancel()
        self._cursor = wx.BusyCursor()
        if raw_string is None:
            raw_string = python_string
        end_line = self.current_prompt_line \
                        + max(1,  len(raw_string.split('\n'))-1)
        for i in range(self.current_prompt_line, end_line):
            self.MarkerAdd(i, _RUNNING_BUFFER_MARKER)
        # Update the display:
        wx.Yield()
        ## Remove the trailing "\n" for cleaner display
        #self.SetSelection(self.GetLength()-1, self.GetLength())
        #self.ReplaceSelection('')
        self.GotoPos(self.GetLength())
        self.__old_raw_input = __builtin__.raw_input
        __builtin__.raw_input = self.raw_input
        PrefilterFrontEnd.execute(self, python_string, raw_string=raw_string)
        __builtin__.raw_input = self.__old_raw_input


    def after_execute(self):
        PrefilterFrontEnd.after_execute(self)
        if hasattr(self, '_cursor'):
            del self._cursor


    def show_traceback(self):
        start_line = self.GetCurrentLine()
        PrefilterFrontEnd.show_traceback(self)
        wx.Yield()
        for i in range(start_line, self.GetCurrentLine()):
            self.MarkerAdd(i, _ERROR_MARKER)
            

    #--------------------------------------------------------------------------
    # Private API
    #--------------------------------------------------------------------------
 

    def _on_key_down(self, event, skip=True):
        """ Capture the character events, let the parent
            widget handle them, and put our logic afterward.
        """
        current_line_number = self.GetCurrentLine()
        if event.KeyCode == ord('('):
            event.Skip()
            self.do_calltip()
        elif self.AutoCompActive():
            event.Skip()
            if event.KeyCode in (wx.WXK_BACK, wx.WXK_DELETE): 
                wx.CallAfter(self.popup_completion, create=True)
            elif not event.KeyCode in (wx.WXK_UP, wx.WXK_DOWN, wx.WXK_LEFT,
                            wx.WXK_RIGHT):
                wx.CallAfter(self.popup_completion)
        else:
            # Up history
            if event.KeyCode == wx.WXK_UP and (
                    ( current_line_number == self.current_prompt_line and
                        event.Modifiers in (wx.MOD_NONE, wx.MOD_WIN) ) 
                    or event.ControlDown() ):
                new_buffer = self.get_history_previous(
                                            self.get_current_edit_buffer())
                if new_buffer is not None:
                    self.replace_current_edit_buffer(new_buffer)
                    if self.GetCurrentLine() > self.current_prompt_line:
                        # Go to first line, for seemless history up.
                        self.GotoPos(self.current_prompt_pos)
            # Down history
            elif event.KeyCode == wx.WXK_DOWN and (
                    ( current_line_number == self.LineCount -1 and
                        event.Modifiers in (wx.MOD_NONE, wx.MOD_WIN) ) 
                    or event.ControlDown() ):
                new_buffer = self.get_history_next()
                if new_buffer is not None:
                    self.replace_current_edit_buffer(new_buffer)
            elif event.KeyCode == ord('\t'):
                last_line = self.get_current_edit_buffer().split('\n')[-1]
                if not re.match(r'^\s*$', last_line):
                    self.do_completion()
                else:
                    event.Skip()
            else:
                ConsoleWidget._on_key_down(self, event, skip=skip)


    def _on_key_up(self, event, skip=True):
        if event.KeyCode == 59:
            # Intercepting '.'
            event.Skip()
            self.popup_completion(create=True)
        else:
            ConsoleWidget._on_key_up(self, event, skip=skip)


if __name__ == '__main__':
    class MainWindow(wx.Frame):
        def __init__(self, parent, id, title):
            wx.Frame.__init__(self, parent, id, title, size=(300,250))
            self._sizer = wx.BoxSizer(wx.VERTICAL)
            self.shell = IPythonWxController(self)
            self._sizer.Add(self.shell, 1, wx.EXPAND)
            self.SetSizer(self._sizer)
            self.SetAutoLayout(1)
            self.Show(True)

    app = wx.PySimpleApp()
    frame = MainWindow(None, wx.ID_ANY, 'Ipython')
    frame.shell.SetFocus()
    frame.SetSize((680, 460))
    self = frame.shell

    app.MainLoop()

