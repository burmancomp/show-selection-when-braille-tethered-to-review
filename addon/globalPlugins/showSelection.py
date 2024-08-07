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
	TetherTo,
)
from cursorManager import CursorManager
from editableText import (
	EditableText,
	EditableTextWithoutAutoSelectDetection,
)
from logHandler import log


def _selectionHelper(self) -> textInfos.TextInfo:
	"""Helper function to decide what should be regarded as selection.
	:return: it may vary between real selection, part of real selection and
	review position (when there is no selection or review position is
	outside of selection).
	"""
	self._readingUnitContainsSelectedCharacters = False
	info: textInfos.TextInfo
	try:
		info = self.obj.makeTextInfo(textInfos.POSITION_SELECTION)
	except (LookupError, RuntimeError):
		self._realSelection = None
		return self._collapsedReviewPosition()
	if info.isCollapsed:
		# Cursor
		self._realSelection = None
		return self._collapsedReviewPosition()
	# Selection
	if (
		self._realSelection is None
		or self._realSelection.start != info.start
		or self._realSelection.end != info.end
	):
		# Selection changed
		self._realSelection = info.copy()
		if config.conf["reviewCursor"]["followCaret"]:
			# Update also review position
			self._fakeSelection = info.copy()
			if self.obj.isTextSelectionAnchoredAtStart:
				# The end of the range is exclusive, so make it inclusive first.
				info.move(textInfos.UNIT_CHARACTER, -1, "end")
			# Collapse the selection to the unanchored end which is also review position.
			info.collapse(end=self.obj.isTextSelectionAnchoredAtStart)
			# Enqueue to avoid recursion error when reviewing different object
			queueHandler.queueFunction(queueHandler.eventQueue, self._setCursor, info)
			return self._fakeSelection
	# Selection unchanged or review does not follow caret
	readingInfo: textInfos.TextInfo = api.getReviewPosition().copy()
	readingInfo.expand(self._getReadingUnit())
	if readingInfo.start >= info.end or readingInfo.end <= info.start:
		# Reading unit containing review position is outside of selection
		return self._collapsedReviewPosition()
	else:
		# Reading unit contains selected charactersbut all characters are not
		# necessarily selected
		if readingInfo.start < self._realSelection.start:
			readingInfo.start = self._realSelection.start
		if readingInfo.end > self._realSelection.end:
			readingInfo.end = self._realSelection.end
		self._readingUnitContainsSelectedCharacters = True
		return readingInfo


def _getSelection(self) -> textInfos.TextInfo:
	"""Gets selection for use in update function.
	:return: when review position is within selection, whole real selection
	is returned if it fits to reading unit, or part of it if it does not.
	When review position is outside of selection or there is no selection
	review position is returned.
	Logic which defines what to return is in _selectionHelper
	and update functions.
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
	info.collapse()
	return info


def update(self) -> None:
	"""Updates this region."""
	self._fakeSelection = self._getSelection()
	if self._readingUnitContainsSelectedCharacters:
		# Braille cursor position is at most self._currentContentPos
		# Get braille cursor position so that braille can be scrolled correctly.
		fakeSelection: textInfos.TextInfo = self._fakeSelection.copy()
		# It is obtained when parent class update function detects cursor.
		# If it detects selection brailleCursorPos is None.
		self._fakeSelection = self._collapsedReviewPosition()
		super(ReviewTextInfoRegion, self).update()
		if self._currentContentPos:
			scrollPos: int = (
				self.brailleCursorPos
				if self.brailleCursorPos < self._currentContentPos - 1
				else self._currentContentPos - 1
			)
			self._fakeSelection = fakeSelection
			# Update region with selection
			super(ReviewTextInfoRegion, self).update()
			# Note: brailleSelectionStart and brailleSelectionEnd are used here to
			# define where braille display should be scrolled based on review position
			# within reading unit which contains at least one selected character. They
			# are also used in scrollToCursorOrSelection function when there is selection
			# so when using them here, there is no need to modify that function.
			self.brailleSelectionStart = scrollPos
			self.brailleSelectionEnd = scrollPos + 1
	else:
		super(ReviewTextInfoRegion, self).update()
	self._fakeSelection = None


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
	if (
		not braille.handler.enabled
		or config.conf["braille"]["mode"] == BrailleMode.SPEECH_OUTPUT.value
		or config.conf["braille"]["tetherTo"] != TetherTo.REVIEW.value
	):
		# Original function
		CursorManager._originalSelectionMovementScriptHelper(self, unit, direction, toPosition)
		return
	reviewPosition = api.getReviewPosition().copy()
	oldSelection = self.selection
	# Original function
	CursorManager._originalSelectionMovementScriptHelper(self, unit, direction, toPosition)
	currentSelection = self.selection
	if oldSelection == currentSelection:
		log.debug("Restore review position")
		api.setReviewPosition(reviewPosition)


def detectPossibleSelectionChange(self) -> None:
	"""If selection has changed, change is spoken and displayed in braille."""
	# Original function
	EditableText._detectPossibleSelectionChange(self)
	if (
		not braille.handler.enabled
		or config.conf["braille"]["mode"] == BrailleMode.SPEECH_OUTPUT.value
		or config.conf["braille"]["tetherTo"] != TetherTo.REVIEW.value
	):
		return
	# Selection change was not always updated to braille.
	# Processing pending events seems to help.
	log.debug("Process pending events")
	api.processPendingEvents(processEventQueue=False)


def reportSelectionChange(self, oldTextInfo: textInfos.TextInfo) -> None:
	"""Reports selection change.
	:param oldTextInfo: selection before change
	"""
	# Original function
	EditableTextWithoutAutoSelectDetection._reportSelectionChange(self, oldTextInfo)
	if (
		not braille.handler.enabled
		or config.conf["braille"]["mode"] == BrailleMode.SPEECH_OUTPUT.value
		or config.conf["braille"]["tetherTo"] != TetherTo.REVIEW.value
	):
		return
	# Braille did not always update at least in word 2019 with IAccessible
	if not eventHandler.isPendingEvents("caret"):
		log.debug("Execute event_caret")
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
