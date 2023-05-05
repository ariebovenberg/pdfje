# This file has been taken from:
# github.com/adobe-type-tools/kern-dump/blob/main/getKerningPairsFromOTF.py
# under its MIT license:

# Copyright (c) 2013-2016 Adobe Systems Incorporated. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# The following changes have been made to the original file:
# - Removed the main function and the command line argument parsing
# - Removed the print statements
# - OTFKernReader takes a TTFont object as input instead of a path
# - added a `for_font` helper method
# - formatted with black and isort

from typing import Mapping

from fontTools import ttLib

kKernFeatureTag = "kern"
kGPOStableName = "GPOS"


class myLeftClass:
    def __init__(self):
        self.glyphs = []
        self.class1Record = 0


class myRightClass:
    def __init__(self):
        self.glyphs = []
        self.class2Record = 0


def collect_unique_kern_lookup_indexes(featureRecord):
    unique_kern_lookups = []
    for featRecItem in featureRecord:
        # GPOS feature tags (e.g. kern, mark, mkmk, size) of each ScriptRecord
        if featRecItem.FeatureTag == kKernFeatureTag:
            feature = featRecItem.Feature

            for featLookupItem in feature.LookupListIndex:
                if featLookupItem not in unique_kern_lookups:
                    unique_kern_lookups.append(featLookupItem)

    return unique_kern_lookups


class OTFKernReader(object):
    def __init__(self, font):
        self.font = font
        self.kerningPairs = {}
        self.singlePairs = {}
        self.classPairs = {}
        self.pairPosList = []
        self.allLeftClasses = {}
        self.allRightClasses = {}

        if kGPOStableName not in self.font:
            self.goodbye()

        else:
            self.analyzeFont()
            self.findKerningLookups()
            self.getPairPos()
            self.getSinglePairs()
            self.getClassPairs()

    def goodbye(self):
        return

    def analyzeFont(self):
        self.gposTable = self.font[kGPOStableName].table
        self.scriptList = self.gposTable.ScriptList
        self.featureList = self.gposTable.FeatureList
        self.featureCount = self.featureList.FeatureCount
        self.featureRecord = self.featureList.FeatureRecord

        self.unique_kern_lookups = collect_unique_kern_lookup_indexes(
            self.featureRecord
        )

    def findKerningLookups(self):
        if not len(self.unique_kern_lookups):
            self.goodbye()

        self.lookup_list = self.gposTable.LookupList
        self.lookups = []
        for kern_lookup_index in sorted(self.unique_kern_lookups):
            lookup = self.lookup_list.Lookup[kern_lookup_index]

            # Confirm this is a GPOS LookupType 2; or
            # using an extension table (GPOS LookupType 9):

            """
            Lookup types:
            1   Single adjustment           Adjust position of a single glyph
            2   Pair adjustment             Adjust position of a pair of glyphs
            3   Cursive attachment          Attach cursive glyphs
            4   MarkToBase attachment       Attach a combining mark to a base glyph
            5   MarkToLigature attachment   Attach a combining mark to a ligature
            6   MarkToMark attachment       Attach a combining mark to another mark
            7   Context positioning         Position one or more glyphs in context
            8   Chained Context positioning Position one or more glyphs in chained context
            9   Extension positioning       Extension mechanism for other positionings
            10+ Reserved for future use
            """

            if lookup.LookupType not in [2, 9]:
                continue
            self.lookups.append(lookup)

    def getPairPos(self):
        for lookup in self.lookups:
            for subtableItem in lookup.SubTable:
                if subtableItem.LookupType == 9:  # extension table
                    if subtableItem.ExtensionLookupType == 8:  # contextual
                        continue
                    elif subtableItem.ExtensionLookupType == 2:
                        subtableItem = subtableItem.ExtSubTable

                self.pairPosList.append(subtableItem)

                # Each glyph in this list will have a corresponding PairSet
                # which will contain all the second glyphs and the kerning
                # value in the form of PairValueRecord(s)
                # self.firstGlyphsList.extend(subtableItem.Coverage.glyphs)

    def getSinglePairs(self):
        for pairPos in self.pairPosList:
            if pairPos.Format == 1:
                # single pair adjustment

                firstGlyphsList = pairPos.Coverage.glyphs

                # This iteration is done by index so we have a way
                # to reference the firstGlyphsList:
                for ps_index, _ in enumerate(pairPos.PairSet):
                    for pairValueRecordItem in pairPos.PairSet[
                        ps_index
                    ].PairValueRecord:
                        secondGlyph = pairValueRecordItem.SecondGlyph
                        valueFormat = pairPos.ValueFormat1

                        if valueFormat == 5:  # RTL kerning
                            kernValue = "<%d 0 %d 0>" % (
                                pairValueRecordItem.Value1.XPlacement,
                                pairValueRecordItem.Value1.XAdvance,
                            )
                        elif valueFormat == 0:  # RTL pair with value <0 0 0 0>
                            kernValue = "<0 0 0 0>"
                        elif valueFormat == 4:  # LTR kerning
                            kernValue = pairValueRecordItem.Value1.XAdvance
                        else:
                            continue  # skip the rest

                        self.kerningPairs[
                            (firstGlyphsList[ps_index], secondGlyph)
                        ] = kernValue
                        self.singlePairs[
                            (firstGlyphsList[ps_index], secondGlyph)
                        ] = kernValue

    def getClassPairs(self):
        for loop, pairPos in enumerate(self.pairPosList):
            if pairPos.Format == 2:
                leftClasses = {}
                rightClasses = {}

                # Find left class with the Class1Record index="0".
                # This first class is mixed into the "Coverage" table
                # (e.g. all left glyphs) and has no class="X" property
                # that is why we have to find the glyphs in that way.

                lg0 = myLeftClass()

                # list of all glyphs kerned to the left of a pair:
                allLeftGlyphs = pairPos.Coverage.glyphs
                # list of all glyphs contained in left-sided kerning classes:
                # allLeftClassGlyphs = pairPos.ClassDef1.classDefs.keys()

                singleGlyphs = []
                classGlyphs = []

                for gName, classID in pairPos.ClassDef1.classDefs.items():
                    if classID == 0:
                        singleGlyphs.append(gName)
                    else:
                        classGlyphs.append(gName)
                # coverage glyphs minus glyphs in real class (without class 0)
                lg0.glyphs = list(set(allLeftGlyphs) - set(classGlyphs))

                lg0.glyphs.sort()
                leftClasses[lg0.class1Record] = lg0
                className = "class_%s_%s" % (loop, lg0.class1Record)
                self.allLeftClasses[className] = lg0.glyphs

                # Find all the remaining left classes:
                for leftGlyph in pairPos.ClassDef1.classDefs:
                    class1Record = pairPos.ClassDef1.classDefs[leftGlyph]

                    if class1Record != 0:  # this was the crucial line.
                        lg = myLeftClass()
                        lg.class1Record = class1Record
                        leftClasses.setdefault(class1Record, lg).glyphs.append(
                            leftGlyph
                        )
                        self.allLeftClasses.setdefault(
                            "class_%s_%s" % (loop, lg.class1Record), lg.glyphs
                        )

                # Same for the right classes:
                for rightGlyph in pairPos.ClassDef2.classDefs:
                    class2Record = pairPos.ClassDef2.classDefs[rightGlyph]
                    rg = myRightClass()
                    rg.class2Record = class2Record
                    rightClasses.setdefault(class2Record, rg).glyphs.append(
                        rightGlyph
                    )
                    self.allRightClasses.setdefault(
                        "class_%s_%s" % (loop, rg.class2Record), rg.glyphs
                    )

                for record_l in leftClasses:
                    for record_r in rightClasses:
                        if pairPos.Class1Record[record_l].Class2Record[
                            record_r
                        ]:
                            valueFormat = pairPos.ValueFormat1

                            if valueFormat in [4, 5]:
                                kernValue = (
                                    pairPos.Class1Record[record_l]
                                    .Class2Record[record_r]
                                    .Value1.XAdvance
                                )
                            elif valueFormat == 0:
                                # valueFormat zero is caused by a value of <0 0 0 0> on a class-class pair; skip these
                                continue
                            else:
                                continue  # skip the rest

                            if kernValue != 0:
                                leftClassName = "class_%s_%s" % (
                                    loop,
                                    leftClasses[record_l].class1Record,
                                )
                                rightClassName = "class_%s_%s" % (
                                    loop,
                                    rightClasses[record_r].class2Record,
                                )

                                self.classPairs[
                                    (leftClassName, rightClassName)
                                ] = kernValue

                                for l in leftClasses[record_l].glyphs:
                                    for r in rightClasses[record_r].glyphs:
                                        if (l, r) in self.kerningPairs:
                                            # if the kerning pair has already been assigned in pair-to-pair kerning
                                            continue
                                        else:
                                            if valueFormat == 5:  # RTL kerning
                                                kernValue = "<%d 0 %d 0>" % (
                                                    pairPos.Class1Record[
                                                        record_l
                                                    ]
                                                    .Class2Record[record_r]
                                                    .Value1.XPlacement,
                                                    pairPos.Class1Record[
                                                        record_l
                                                    ]
                                                    .Class2Record[record_r]
                                                    .Value1.XAdvance,
                                                )

                                            self.kerningPairs[
                                                (l, r)
                                            ] = kernValue


def for_font(f: ttLib.TTFont) -> Mapping[tuple[str, str], float]:
    reader = OTFKernReader(f)
    glyph_name_to_char = {
        gname: chr(ord_) for ord_, gname in f.getBestCmap().items()
    }
    return {
        (glyph_name_to_char[a], glyph_name_to_char[b]): v
        for (a, b), v in reader.kerningPairs.items()
        if a in glyph_name_to_char and b in glyph_name_to_char
    }
