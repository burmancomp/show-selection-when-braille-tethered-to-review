# Show selection when braille tethered to review
# Copyright 2024 Burman's Computer and Education Ltd.
# Released under GPL v2.

import globalPluginHandler
import braille
import api
import textInfos
import config
import eventHandler
import queueHandler

from braille import (
	ReviewTextInfoRegion,
	_routingShouldMoveSystemCaret,
)
from config.configFlags import (
	BrailleMode,
)
from cursorManager import CursorManager
from editableText import (
	EditableText,
	EditableTextWithoutAutoSelectDetection,
)


def _selectionHelper(self) -> textInfos.TextInfo:
	"""Helper function for _getSelection function.
	:return: may vary between real selection, part of real selection and
	review position (when there is no selection or review position is
	outside of selection).
	"""
	try:
		info: textInfos.TextInfo = self.obj.makeTextInfo(textInfos.POSITION_SELECTION)
	except (LookupError, RuntimeError):
		self._realSelection = None
		return self._collapsedReviewPosition()
	# Cursor
	if info.isCollapsed:
		self._realSelection = None
		return self._collapsedReviewPosition()
	# Selection changed
	if (
		self._realSelection is None
		or self._realSelection.start != info.start
		or self._realSelection.end != info.end
	):
		self._realSelection = info
		# Update also review position if review follows caret
		if config.conf["reviewCursor"]["followCaret"]:
			info = info.copy()
			if self.obj.isTextSelectionAnchoredAtStart:
				# The end of the range is exclusive, so make it inclusive first.
				info.move(textInfos.UNIT_CHARACTER, -1, "end")
			# Collapse the selection to the unanchored end which is also review position.
			info.collapse(end=self.obj.isTextSelectionAnchoredAtStart)
			# To avoid recursion error when reviewing different object
			queueHandler.queueFunction(queueHandler.eventQueue, self._setCursor, info)
			return self._realSelection
	# Selection unchanged or review does not follow caret
	readingInfo: textInfos.TextInfo = self._collapsedReviewPosition()
	readingInfo.expand(self._getReadingUnit())
	# Reading unit containing review position is outside of selection
	if readingInfo.start > info.end or readingInfo.end < info.start:
		return self._collapsedReviewPosition()
	# Reading unit contains selected characters but all characters are not
	# necessarily selected
	else:
		if readingInfo.start < info.start:
			readingInfo.start = info.start
		if readingInfo.end > info.end:
			readingInfo.end = info.end
		self._readingUnitContainsSelectedCharacters = True
		return readingInfo


def _getSelection(self) -> textInfos.TextInfo:
	"""Gets selection for use in update function.
	:return: if _fakeSelection is not None, it is returned. This makes possible
	to pretend that there is no selection (needed in update function).
	Logic which defines what to return, when _fakeSelection is None, is in
	_selectionHelper function.
	"""
	if self._fakeSelection is not None:
		return self._fakeSelection
	return self._selectionHelper()


def _collapsedReviewPosition(self) -> textInfos.TextInfo:
	"""Gets collapsed review position.
	:return: collapsed review position
	"""
	info: textInfos.TextInfo = api.getReviewPosition().copy()
	# Info should be collapsed, but it is not always, at least when
	# switching from focus mode to browse mode.
	if not info.isCollapsed:
		info.collapse()
	return info


def update(self) -> None:
	"""Updates this region."""
	self._fakeSelection = None
	self._readingUnitContainsSelectedCharacters = False
	fakeSelection: textInfos.TextInfo = self._getSelection()
	# Within selection
	if self._readingUnitContainsSelectedCharacters:
		# Get braille cursor position so that braille can be scrolled correctly.
		# It is obtained when parent class update function detects cursor.
		# If it detects selection brailleCursorPos is None.
		self._fakeSelection = self._collapsedReviewPosition()
		super(ReviewTextInfoRegion, self).update()
		brailleCursorPos: int = self.brailleCursorPos
		# Update region with selection
		self._fakeSelection = fakeSelection
		super(ReviewTextInfoRegion, self).update()
		# Update succeeded
		if self.brailleCursorPos is None:
			# brailleSelectionStart and brailleSelectionEnd are set here to define
			# appropriate braille display scrolling when moving to reading unit
			# which contains one or more selected characters.
			# They are then used in braille.BrailleHandler.scrollToCursorOrSelection
			# function for this.
			scrollPos: int = min(brailleCursorPos, len(self.brailleCells) - 1)
			self.brailleSelectionStart = scrollPos
			self.brailleSelectionEnd = scrollPos + 1
		# Failed to detect selection, revert to review position
		else:
			self._fakeSelection = self._collapsedReviewPosition()
			super(ReviewTextInfoRegion, self).update()
	# Selection changed, outside of selection or no selection
	else:
		super(ReviewTextInfoRegion, self).update()


def _routeToTextInfoHelper(self, info: textInfos.TextInfo) -> None:
	"""Helper function.
	:param info: position where cursor should be moved
	When within selection, function activates position with second press,
	if routing does not move caret.
	Then original function is executed.
	"""
	if (
		self._readingUnitContainsSelectedCharacters
		and info.start == api.getReviewPosition().start
		and not _routingShouldMoveSystemCaret()
	):
		info.activate()
	ReviewTextInfoRegion._originalRouteToTextInfo(self, info)


def _selectionMovementScriptHelper(
	self, unit: str | None = None, direction: int | None = None, toPosition: str | None = None
) -> None:
	"""Helper function.
	:param unit: movement unit
	:param direction: direction to move
	:param toPosition: position to move
	In addition, to execution of original function, review position is stored
	and restored when appropriate.
	"""
	if not braille.handler.enabled or config.conf["braille"]["mode"] == BrailleMode.SPEECH_OUTPUT.value:
		# Original function
		CursorManager._originalSelectionMovementScriptHelper(self, unit, direction, toPosition)
		return
	reviewPosition: textInfos.TextInfo = api.getReviewPosition().copy()
	oldSelection: textInfos.TextInfo = self.selection
	# Original function
	CursorManager._originalSelectionMovementScriptHelper(self, unit, direction, toPosition)
	currentSelection: textInfos.TextInfo = self.selection
	if oldSelection == currentSelection:
		api.setReviewPosition(reviewPosition)


def detectPossibleSelectionChange(self) -> None:
	"""If selection has changed, change is spoken and displayed in braille."""
	# Original function
	EditableText._detectPossibleSelectionChange(self)
	if not braille.handler.enabled or config.conf["braille"]["mode"] == BrailleMode.SPEECH_OUTPUT.value:
		return
	# Selection change was not always updated to braille.
	# Processing pending events seems to help.
	api.processPendingEvents(processEventQueue=False)


def reportSelectionChange(self, oldTextInfo: textInfos.TextInfo) -> None:
	"""Reports selection change.
	:param oldTextInfo: selection before change
	"""
	# Original function
	EditableTextWithoutAutoSelectDetection._reportSelectionChange(self, oldTextInfo)
	if not braille.handler.enabled or config.conf["braille"]["mode"] == BrailleMode.SPEECH_OUTPUT.value:
		return
	# Braille did not always update at least in word 2019 with IAccessible
	if not eventHandler.isPendingEvents("caret"):
		self.event_caret()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		"""Constructor.
		Some class variables are added and replaced to get selection to be shown.
		"""
		super().__init__()
		ReviewTextInfoRegion._realSelection: textInfos.TextInfo | None = None
		ReviewTextInfoRegion._fakeSelection: textInfos.TextInfo | None = None
		ReviewTextInfoRegion._readingUnitContainsSelectedCharacters: bool = False
		ReviewTextInfoRegion._originalRouteToTextInfo = ReviewTextInfoRegion._routeToTextInfo
		ReviewTextInfoRegion._routeToTextInfo = _routeToTextInfoHelper
		ReviewTextInfoRegion._selectionHelper = _selectionHelper
		ReviewTextInfoRegion._collapsedReviewPosition = _collapsedReviewPosition
		ReviewTextInfoRegion._getSelection = _getSelection
		ReviewTextInfoRegion.update = update
		CursorManager._originalSelectionMovementScriptHelper = CursorManager._selectionMovementScriptHelper
		CursorManager._selectionMovementScriptHelper = _selectionMovementScriptHelper
		EditableText._detectPossibleSelectionChange = EditableText.detectPossibleSelectionChange
		EditableText.detectPossibleSelectionChange = detectPossibleSelectionChange
		EditableTextWithoutAutoSelectDetection._reportSelectionChange = (
			EditableTextWithoutAutoSelectDetection.reportSelectionChange
		)
		EditableTextWithoutAutoSelectDetection.reportSelectionChange = reportSelectionChange
