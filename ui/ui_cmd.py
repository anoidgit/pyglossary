# -*- coding: utf-8 -*-
# ui_cmd.py
#
# Copyright © 2008-2019 Saeed Rasooli <saeed.gnu@gmail.com> (ilius)
# This file is part of PyGlossary project, https://github.com/ilius/pyglossary
#
# This program is a free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. Or on Debian systems, from /usr/share/common-licenses/GPL
# If not, see <http://www.gnu.org/licenses/gpl.txt>.

from os.path import join
import time
import signal

from tqdm import tqdm

from pyglossary.glossary import *
from pyglossary.reverse import reverseGlossary
from .base import *
from . import progressbar as pb
from .wcwidth import wcswidth


def wc_ljust(text, length, padding=' '):
	return text + padding * max(0, (length - wcswidth(text)))


if os.sep == "\\":  # Operating system is Windows
	startRed = ""
	endFormat = ""
	startBold = ""
	startUnderline = ""
	endFormat = ""
else:
	startRed = "\x1b[31m"
	endFormat = "\x1b[0;0;0m"

	startBold = "\x1b[1m"  # Start Bold # len=4
	startUnderline = "\x1b[4m"  # Start Underline # len=4
	endFormat = "\x1b[0;0;0m"  # End Format # len=8
	# redOnGray = "\x1b[0;1;31;47m"


COMMAND = "pyglossary"
# COMMAND = sys.argv[0]


def getColWidth(subject, strings):
	return max(
		len(x) for x in [subject] + strings
	)


def getFormatsTable(names, header):
	descriptions = [
		Glossary.plugins[name].description
		for name in names
	]
	extensions = [
		" ".join(Glossary.plugins[name].extensions)
		for name in names
	]

	nameWidth = getColWidth("Name", names)
	descriptionWidth = getColWidth("Description", descriptions)
	extensionsWidth = getColWidth("Extensions", extensions)

	lines = ["\n"]
	lines.append(startBold + header + endFormat)

	lines.append(
		" | ".join([
			"Name".center(nameWidth),
			"Description".center(descriptionWidth),
			"Extensions".center(extensionsWidth)
		])
	)
	lines.append(
		"-+-".join([
			"-" * nameWidth,
			"-" * descriptionWidth,
			"-" * extensionsWidth,
		])
	)
	for index, name in enumerate(names):
		lines.append(
			" | ".join([
				name.ljust(nameWidth),
				descriptions[index].ljust(descriptionWidth),
				extensions[index].ljust(extensionsWidth)
			])
		)

	return "\n".join(lines)


def help():
	import string
	with open(join(dataDir, "help")) as fp:
		text = fp.read()
	text = text.replace("<b>", startBold)\
		.replace("<u>", startUnderline)\
		.replace("</b>", endFormat)\
		.replace("</u>", endFormat)
	text = string.Template(text).substitute(
		CMD=COMMAND,
	)
	text += getFormatsTable(Glossary.readFormats, "Supported input formats:")
	text += getFormatsTable(Glossary.writeFormats, "Supported output formats:")
	print(text)


def parseFormatOptionsStr(st):
	st = st.strip()
	if not st:
		return {}

	opt = {}
	parts = st.split(";")
	for part in parts:
		try:
			(key, value) = part.split("=")
		except ValueError:
			log.error(f"bad option syntax: {part}")
			continue
		key = key.strip()
		value = value.strip()
		opt[key] = value
	return opt


class NullObj(object):
	def __getattr__(self, attr):
		return self

	def __setattr__(self, attr, value):
		pass

	def __setitem__(self, key, value):
		pass

	def __call__(self, *args, **kwargs):
		pass


class MyTqdm(tqdm):
	@property
	def format_dict(self):
		d = super(MyTqdm, self).format_dict
		"""
		return dict(
			n=self.n, total=self.total,
			elapsed=self._time() - self.start_t
			if hasattr(self, 'start_t') else 0,
			ncols=ncols, nrows=nrows,
			prefix=self.desc, ascii=self.ascii, unit=self.unit,
			unit_scale=self.unit_scale,
			rate=1 / self.avg_time if self.avg_time else None,
			bar_format=self.bar_format, postfix=self.postfix,
			unit_divisor=self.unit_divisor, initial=self.initial,
			colour=self.colour,
		)
		"""
		d["bar_format"] = "{desc}: %{percentage:04.1f} |{bar}|[{elapsed}<{remaining}, {rate_fmt}{postfix}]"
		"""
		Possible vars:
			l_bar, bar, r_bar, n, n_fmt, total, total_fmt,
			percentage, elapsed, elapsed_s, ncols, nrows, desc, unit,
			rate, rate_fmt, rate_noinv, rate_noinv_fmt,
			rate_inv, rate_inv_fmt, postfix, unit_divisor,
			remaining, remaining_s.
		"""
		return d


class UI(UIBase):
	def __init__(self, **options):
		self.pref = {}
		# log.debug(self.pref)
		self.pbar = NullObj()
		self._toPause = False
		self._resetLogFormatter = None

	def onSigInt(self, *args):
		log.info("")
		if self._toPause:
			log.info("Operation Canceled")
			sys.exit(0)
		else:
			self._toPause = True
			log.info("Please wait...")

	def setText(self, text):
		self.pbar.widgets[0] = text

	def fixLogger(self):
		for h in log.handlers:
			if h.name == "std":
				self.fixLogHandler(h)
				return

	def fillMessage(self, msg):
		return "\r" + wc_ljust(msg, self.pbar.ncols)

	def fixLogHandler(self, h):
		def reset():
			h.formatter.fill = None

		self._resetLogFormatter = reset
		h.formatter.fill = self.fillMessage

	def progressInit(self, title):
		self.pbar = MyTqdm(
			total=1.0,
			desc=title,
		)
		"""
		rot = pb.RotatingMarker()
		self.pbar = pb.ProgressBar(
			maxval=1.0,
			# update_step=0.5, removed
		)
		self.pbar.widgets = [
			title + " ",
			pb.AnimatedMarker(),
			" ",
			pb.Bar(marker="█"),
			pb.Percentage(), " ",
			pb.ETA(),
		]
		self.pbar.start(num_intervals=1000)
		rot.pbar = self.pbar
		"""
		self.fixLogger()

	def progress(self, rat, text=""):
		self.pbar.update(rat - self.pbar.n)

	def progressEnd(self):
		self.pbar.close()
		if self._resetLogFormatter:
			self._resetLogFormatter()

	def reverseLoop(self, *args, **kwargs):
		reverseKwArgs = {}
		for key in (
			"words",
			"matchWord",
			"showRel",
			"includeDefs",
			"reportStep",
			"saveStep",
			"maxNum",
			"minRel",
			"minWordLen"
		):
			try:
				reverseKwArgs[key] = self.pref["reverse_" + key]
			except KeyError:
				pass
		reverseKwArgs.update(kwargs)

		if not self._toPause:
			log.info("Reversing glossary... (Press Ctrl+C to pause/stop)")
		for wordI in reverseGlossary(self.glos, **reverseKwArgs):
			if self._toPause:
				log.info(
					"Reverse is paused."
					" Press Enter to continue, and Ctrl+C to exit"
				)
				input()
				self._toPause = False

	def run(
		self,
		inputFilename,
		outputFilename="",
		inputFormat="",
		outputFormat="",
		reverse=False,
		prefOptions=None,
		readOptions=None,
		writeOptions=None,
		convertOptions=None,
	):
		if not prefOptions:
			prefOptions = {}
		if not readOptions:
			readOptions = {}
		if not writeOptions:
			writeOptions = {}
		if not convertOptions:
			convertOptions = {}

		self.pref_load(**prefOptions)

		if inputFormat:
			# inputFormat = inputFormat.capitalize()
			if inputFormat not in Glossary.readFormats:
				log.error(f"invalid read format {inputFormat}")
		if outputFormat:
			# outputFormat = outputFormat.capitalize()
			if outputFormat not in Glossary.writeFormats:
				log.error(f"invalid write format {outputFormat}")
				log.error(f"try: {COMMAND} --help")
				return 1
		if not outputFilename:
			if reverse:
				pass
			elif outputFormat:
				try:
					ext = Glossary.plugins[outputFormat].extensions[0]
				except (KeyError, IndexError):
					log.error(f"invalid write format {outputFormat}")
					log.error(f"try: {COMMAND} --help")
					return 1
				else:
					outputFilename = os.path.splitext(inputFilename)[0] + ext
			else:
				log.error("neither output file nor output format is given")
				log.error(f"try: {COMMAND} --help")
				return 1

		glos = self.glos = Glossary(ui=self)
		if reverse:
			signal.signal(signal.SIGINT, self.onSigInt)  # good place? FIXME
			readOptions["direct"] = True
			if not glos.read(
				inputFilename,
				format=inputFormat,
				**readOptions
			):
				log.error("reading input file was failed!")
				return False
			self.setText("Reversing: ")
			self.pbar.update_step = 0.1
			self.reverseLoop(savePath=outputFilename)
		else:
			finalOutputFile = self.glos.convert(
				inputFilename,
				inputFormat=inputFormat,
				outputFilename=outputFilename,
				outputFormat=outputFormat,
				readOptions=readOptions,
				writeOptions=writeOptions,
				**convertOptions
			)
			return bool(finalOutputFile)

		return True
