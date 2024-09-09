# Show selection when braille is tethered to review

## Good to know before using this addon

This is a beta version, and there may be issues. There are likely very few testers which means that more or less use cases are not tested. One such case is using braille input.

When this addon is enabled:

* If braille is in use, braille is tethered to review and review follows caret,
review position is changed when selection changes.
* When there are one or more selected characters on the line you are reviewing,
there is no braille cursor. This means that you cannot see exact review position
from braille display then.
* when "Show selection" in NVDA settings Braille category is disabled, you
cannot exactly see from braille display what is selected.

## General

To use this addon, tether braille to review in NVDA settings Braille category.
You likely want also that review cursor follows system caret most of time
(see NVDA settings Review Cursor category). Selection is shown in edit controls
and documents with dots 7 and 8 when "Show selection" is enabled in NVDA
settings Braille category. To see selection outside of edit controls,
browse mode should be used.

You can easily see what you have selected for example for copying or formatting
in text editor. You can move around edit control or document with braille
gestures and text review commands which move braille display. Movement does not
affect on caret, and it is not restricted to selected text. It means that
you can investigate both selected and unselected part of text with braille.
You can use routing buttons to move review position and/or caret according to 
NVDA Braille category "Move system caret when routing review cursor" setting.