# -*- coding: utf-8 -*-
import bibledata
from collections import defaultdict

## To do ##
#Move Passage.__init__ checks elsewhere
#Make PassageCollection object to be list-like
#__add__ should return Passage if second passage starts immediately after first passage

## Long term ##
#Implement string parsing



class Passage:
    def __init__(self, book, start_chapter=None, start_verse=None, end_chapter=None, end_verse=None, translation="ESV"):
        """
        Intialise and check passage reference. Missing information is filled in where it can be
        safely assumed. Infeasible passages will raise InvalidPassageException.
        
        'book' may be a name (e.g. "Genesis"), a standard abbreviation (e.g. "Gen") or an
        integer (i.e. Genesis = 1, Revelation = 66).
        """
        self.bd = bd = bible_data(translation)

        #Set self values and check book
        self.start_chapter = start_chapter
        self.start_verse = start_verse
        self.end_chapter = end_chapter
        self.end_verse = end_verse
        if isinstance(book, int) or isinstance(book, long): #Book has been provided as an integer (1-66)
            self.book_n = int(book)
            if self.book_n > 66 or self.book_n < 1:
                raise InvalidPassageException()
        else: #Assume book has been provided as a string
            self.book_n = bd.book_numbers.get(str(book).upper(),None)
            if self.book_n == None:
                raise InvalidPassageException()

        #Check which numbers have been provided.
        sc = sv = ec = ev = True
        if start_chapter == None: sc = False
        if start_verse == None: sv = False
        if end_chapter == None: ec = False
        if end_verse == None: ev = False
        #Require that numbers are not negative.
        if (sc and start_chapter < 1) or (sv and start_verse < 1) or (ec and end_chapter < 1) or (ev and end_verse < 1): raise InvalidPassageException()

        #Now fill out missing information.

        #No chapter/verse information at all: Assume reference was for full book
        if not sc and not sv and not ec and not ev:
            self.start_chapter = self.start_verse = 1
            self.end_chapter = bd.number_chapters[self.book_n]
            self.end_verse = bd.last_verses[self.book_n, self.end_chapter]
            return self.setint()

        if bd.number_chapters[self.book_n] == 1:
            #Single-chapter books
            if not sc and not sv:
                #No start information at all
                self.start_chapter = self.start_verse = 1; sc = sv = True
            if sv and ev and (not sc or self.start_chapter == 1) and (not ec or self.end_chapter == 1):
                #This includes the case where everything is provided and everything is fine
                #and the case where chapters haven't been provided
                self.start_chapter = self.end_chapter = 1
            elif sc and ec and not sv and not ev:
                #Chapter range provided, when it should have been verse range (useful for parsers)
                self.start_verse = self.start_chapter
                self.end_verse = self.end_chapter
                self.start_chapter = self.end_chapter = 1
            elif sc and not ec and not ev:
                if sv:
                    #This allows you to write, for example, Passage('Phm',2,1)
                    self.end_verse = self.start_verse
                else:
                    #This allows you to write, for example, Passage('Phm',2)
                    self.end_verse = self.start_chapter
                self.start_verse = self.start_chapter
                self.start_chapter = self.end_chapter = 1
            elif sv and not sc and not ec and not ev:
                #Only start verse entered. This allows you to quickly and un-ambiguously enter a single-verse reference into a text-box form
                self.end_verse = self.start_verse
                self.start_chapter = self.end_chapter = 1
            else:
                raise InvalidPassageException()
        else:
            #Multi-chapter books
            if not sc: self.start_chapter = 1
            if not sv: self.start_verse = 1
            if not ec: self.end_chapter = self.start_chapter
            if not ev:
                if self.start_chapter == self.end_chapter:
                    if sv:
                        self.end_verse = self.start_verse
                    else:
                        self.end_verse = bd.last_verses.get((self.book_n, self.end_chapter),1) #if chapter doesn't exist, passage won't be valid anyway
                else:
                    if self.end_chapter > bd.number_chapters[self.book_n]:
                        self.end_chapter = bd.number_chapters[self.book_n]
                        #NB: if start chapter doesn't exist, passage won't be valid anyway
                    self.end_verse = bd.last_verses[self.book_n, self.end_chapter]

        #Checking that end chapter and end verse both exist; truncating if necessary
        if self.end_chapter > bd.number_chapters[self.book_n]:
            self.end_chapter = bd.number_chapters[self.book_n]
            self.end_verse = bd.last_verses[self.book_n, self.end_chapter]
        elif self.end_verse > bd.last_verses[self.book_n, self.end_chapter]:
            self.end_verse = bd.last_verses[self.book_n, self.end_chapter]

        #Raise exception now if passage is still invalid
        if self.start_chapter > bd.number_chapters[self.book_n]: raise InvalidPassageException()
        if self.start_verse > bd.last_verses[self.book_n,self.start_chapter]: raise InvalidPassageException()
        if self.start_chapter > self.end_chapter:
            raise InvalidPassageException()
        elif self.start_chapter == self.end_chapter and self.start_verse > self.end_verse:
             raise InvalidPassageException()
        if bd.number_chapters[self.book_n] == 1 and (self.start_chapter > 1 or self.end_chapter > 1): raise InvalidPassageException()

        #Check that start and begining verses both exist; shorten if not
        if self.start_chapter == self.end_chapter:
            missing = bd.missing_verses.get((self.book_n, self.start_chapter),[])
            while self.start_verse in missing:
                if self.start_verse < self.end_verse:
                    self.start_verse += 1
                else: raise InvalidPassageException()
            while self.end_verse in missing:
                self.end_verse -= 1
        else:
            missing_start = bd.missing_verses.get((self.book_n, self.start_chapter),[])
            while self.start_verse in missing_start:
                self.start_verse += 1
            missing_end = bd.missing_verses.get((self.book_n, self.end_chapter),[])
            while self.end_verse in missing_end:
                self.end_verse -= 1
            if self.end_verse < 1:
                self.end_chapter -= 1
                self.end_verse = bd.last_verses[self.book_n, self.end_chapter]
        return self.setint()

    def setint(self):
        """
        Set integers self.start and self.end, in order to represent passage starting and endings in purely numeric form. Primarily useful for efficient database filtering of passages.
        First two numerals are book number (eg. Gen = 01 and Rev = 66). Next three numerals are chapter, and final three numerals are verse. Thus Gen 3:5 is encoded as 001003005.
        """
        self.start = (self.book_n * 10**6) + (self.start_chapter * 10**3) + self.start_verse
        self.end   = (self.book_n * 10**6) + (self.end_chapter * 10**3)   + self.end_verse
        return
    def is_valid(self):
        """ Return boolean denoting whether this Passage object is a valid reference or not. """
        #Does book exist?
        if isinstance(self.book_n, int):
            if self.book_n > 66 or self.book_n < 1:
                return False
        else: return False
        #Are start_chapter, start_verse, end_chapter, and end_verse all integers?
        #if not isinstance(self.start_chapter,int) or not isinstance(self.start_verse,int) or not isinstance(self.end_chapter,int) or not isinstance(self.end_verse,int): return False
        #Is end after start?
        if self.start_chapter > self.end_chapter:
            return False
        elif self.start_chapter == self.end_chapter:
            if self.end_verse < self.start_verse: return False
        #Do end chapter/verse and start verse exist?
        if self.bd.number_chapters[self.book_n] < self.end_chapter: return False
        if self.bd.last_verses[self.book_n, self.end_chapter] < self.end_verse: return False
        if self.bd.last_verses[self.book_n, self.start_chapter] < self.start_verse: return False
        #Are either start or end verses missing verses?
        if self.start_verse in self.bd.missing_verses.get((self.book_n, self.start_chapter),[]): return False
        if self.end_verse in self.bd.missing_verses.get((self.book_n, self.end_chapter),[]): return False #Making implicit assumption that there are no two consecutive missing verses.
        #Everything checked; return True
        return True
    def number_verses(self):
        """ Return number of verses in this passage. """
        if not self.is_valid(): return 0
        if self.start_chapter == self.end_chapter:
            n = self.end_verse - self.start_verse + 1
            missing = self.bd.missing_verses.get((self.book_n,self.start_chapter),[])
            for verse in missing:
                if verse >= self.start_verse and verse <= self.end_verse: n -= 1
            return n
        else:
            n = self.end_verse + (self.bd.last_verses[self.book_n,self.start_chapter] - self.start_verse + 1)
            for chapter in range(self.start_chapter+1,self.end_chapter):
                n += self.bd.last_verses[self.book_n,chapter] - len(self.bd.missing_verses.get((self.book_n,chapter),[]))
            missing_start = self.bd.missing_verses.get((self.book_n,self.start_chapter),[])
            for verse in missing_start:
                if verse >= self.start_verse: n -= 1
            missing_end = self.bd.missing_verses.get((self.book_n,self.end_chapter),[])
            for verse in missing_end:
                if verse <= self.end_verse: n -= 1
            return n
    def proportion_of_book(self):
        """ Return proportion of current book represented by this passage. """
        return len(self)/float(self.book_total_verses())

    def complete_book(self):
        """ Return True if this reference is for a whole book. """
        return (self.start_chapter == self.start_verse == 1 and
                self.end_chapter == self.bd.number_chapters[self.book_n] and
                self.end_verse   == self.bd.last_verses[self.book_n, self.end_chapter])
    
    def complete_chapter(self):
        """ Return True if this reference is for a whole chapter. """
        return (self.start_verse == 1 and
                self.start_chapter == self.end_chapter and
                self.end_verse == self.bd.last_verses[self.book_n, self.end_chapter])

    def truncate(self, number_verses=None, proportion_of_book=None):
        """
        Return truncated version of passage if longer than given restraints, or else return self.

        Arguments:
        number_verses -- Maximum number of verses that passage may be
        proportion_of_book -- Maximum proportion of book that passage may be

        For example:
        >>> Passage('Gen').truncate(number_verses=150)
        Passage(book=1, start_chapter=1, start_verse=1, end_chapter=6, end_verse=12)

        """
        #Check current length and length of limits
        current_length = len(self)
        limit = current_length
        if number_verses != None:
            if number_verses < limit: limit = number_verses
        if proportion_of_book != None:
            verses = int(proportion_of_book * self.book_total_verses())
            if verses < limit: limit = verses
        if current_length <= limit:
            #No need to shorten; return as-is.
            return self
        else:
            #Check that we're non-negative
            if limit < 1: return None
            #We need to shorten this passage. Iterate through passages until we've reached our quota of verses.
            n = 0
            for chapter in range(self.start_chapter, self.end_chapter+1):
                if chapter == self.start_chapter:
                    start_verse = self.start_verse
                else:
                    start_verse = 1
                if chapter == self.end_chapter:
                    end_verse = self.end_verse
                else:
                    end_verse = self.bd.last_verses[self.book_n, chapter]
                valid_verses = [v for v in range(start_verse, end_verse+1) if v not in self.bd.missing_verses.get((self.book_n, chapter),[]) ]
                if n + len(valid_verses) >= limit:
                    return Passage(self.book_n, self.start_chapter, self.start_verse, chapter, valid_verses[limit-n-1])
                else:
                    n += len(valid_verses)
            #If we've got through the loop and haven't returned a Passage object, something's gone amiss.
            raise Exception("Got to end_verse and still hadn't reached current_length!")
    def extend(self, number_verses=None, proportion_of_book=None):
        """
        Return extended version of passage if shorter than given restraints, or else return self.
        Same arguments as used by self.truncate
        
        For example, returning the first 50% of the verses in Genesis:
        >>> Passage('Gen',1,1).extend(proportion_of_book=0.5)
        Passage(book=1, start_chapter=1, start_verse=1, end_chapter=27, end_verse=38)
        
        """
        #First check if starting reference is valid:
        if (self.book_n > 66 or self.book_n < 1) or (self.start_chapter < 1 or self.start_chapter > self.bd.number_chapters[self.book_n]) or (self.start_verse < 1 or self.start_verse > self.bd.last_verses[self.book_n, self.start_chapter]): return None
        #Check current length and length of limits
        current_length = len(self)
        limit = current_length
        if number_verses != None:
            if number_verses > limit: limit = number_verses
        if proportion_of_book != None:
            verses = int(proportion_of_book * self.book_total_verses())
            if verses > limit: limit = verses
        if current_length >= limit:
            #No need to extend; return as-is.
            return self
        else:
            #We need to extend this passage. Do this by truncating the longest passage possible.
            end_chapter = self.bd.number_chapters[self.book_n]
            end_verse = self.bd.last_verses[self.book_n, end_chapter]
            return Passage(self.book_n, self.start_chapter, self.start_verse, end_chapter, end_verse).truncate(number_verses=limit)
    def book_total_verses(self):
        """ Return total number of verses in current book. """
        verses = 0
        for chapter in range(1,self.bd.number_chapters[self.book_n]+1):
            verses += self.bd.last_verses[self.book_n,chapter] - len(self.bd.missing_verses.get((self.book_n,chapter),[]))
        return verses
    def book_name(self, abbreviated = False):
        """ Return full or abbreviated book name. """
        if abbreviated:
            return self.bd.book_names[self.book_n][2]
        else:
            if self.book_n == 19 and self.start_chapter == self.end_chapter:
                return "Psalm"
            else:
                return self.bd.book_names[self.book_n][1]
    def reference_string(self, abbreviated = False, dash = "-"):
        """ Return string representation of Passage object. """
        if not self.is_valid(): return 'Invalid passage'
        if self.bd.number_chapters[self.book_n] == 1:
            if self.start_verse == self.end_verse:
                return self.book_name(abbreviated) + " " + str(self.start_verse)
            elif self.start_verse == 1 and self.end_verse == self.bd.last_verses[self.book_n, 1]:
                return self.book_name(abbreviated)
            else:
                return self.book_name(abbreviated) + " " + str(self.start_verse) + dash + str(self.end_verse)
        else:
            if self.start_chapter == self.end_chapter:
                if self.start_verse == self.end_verse:
                    return self.book_name(abbreviated) + " " + str(self.start_chapter) + ":" + str(self.start_verse)
                elif self.start_verse == 1 and self.end_verse == self.bd.last_verses[self.book_n, self.start_chapter]:
                    return self.book_name(abbreviated) + " " + str(self.start_chapter)
                else:
                    return self.book_name(abbreviated) + " " + str(self.start_chapter) + ":" + str(self.start_verse) + dash + str(self.end_verse)
            else:
                if self.start_verse == 1 and self.end_verse == self.bd.last_verses[self.book_n, self.end_chapter]:
                    if self.start_chapter == 1 and self.end_chapter == self.bd.number_chapters[self.book_n]:
                        return self.book_name(abbreviated)
                    else:
                        return self.book_name(abbreviated) + " " + str(self.start_chapter) + dash + str(self.end_chapter)
                else:
                    return self.book_name(abbreviated) + " " + str(self.start_chapter) + ":" + str(self.start_verse) + dash + str(self.end_chapter) + ":" + str(self.end_verse)
    def __str__(self):
        """
        x.__str__() <==> str(x)
        Return passage string.
        """
        return self.reference_string()
    def __unicode__(self):
        """
        x.__unicode__() <==> unicode(x)
        Return unicode version of passage string, using en-dash for ranges.
        """
        return unicode(self.reference_string(dash=u"–"))
    def abbr(self):
        """ Return abbreviated passage string """
        return self.reference_string(abbreviated=True)
    def uabbr(self):
        """ Return unicode-type abbreviated passage string, using en-dash for ranges. """
        return unicode(self.reference_string(abbreviated=True, dash=u"–"))
    def __len__(self):
        """
        x.__len__() <==> len(x)
        Return number of verses in passage.
        """
        return int(self.number_verses())
    def __repr__(self):
        """
        x.__repr__() <==> x
        """
        return "Passage(book="+repr(self.book_n)+", start_chapter="+repr(self.start_chapter)+", start_verse="+repr(self.start_verse)+", end_chapter="+repr(self.end_chapter)+", end_verse="+repr(self.end_verse)+")"
    def __cmp__(self, other):
        """ Object sorting function. Sorting is based on start chapter/verse. """
        return cmp(self.start, other.start)
    def __eq__(self,other):
        """
        x.__eq__(y) <==> x == y
        Equality checking.
        """
        if not isinstance(other, Passage): return False
        if (self.book_n == other.book_n) and (self.start_chapter == other.start_chapter) and (self.start_verse == other.start_verse) and (self.end_chapter == other.end_chapter) and (self.end_verse == other.end_verse):
            return True
        else:
            return False
    def __ne__(self,other):
        """
        x.__ne__(y) <==> x != y
        Inequality checking.
        """
        return not self.__eq__(other)
    def __add__(self,other):
        """
        x.__add__(y) <==> x + y
        Addition. PassageCollection object returned.
        """
        if isinstance(other,Passage):
            return PassageCollection(self,other)
        elif isinstance(other,PassageCollection):
            return PassageCollection(self,other.passages)
        else:
            return NotImplemented


class PassageCollection:
    def __init__(self,*args):
        """
        PassageCollection initialisation. Passages to be in collection may be passed in directly or as lists.
        For example, the following is valid:
        PassageCollection( Passage('Gen'), Passage('Exo'), [Passage('Mat'), Passage('Mar')])
        """
        self.passages = []
        for arg in args:
            if isinstance(arg, Passage):
                self.passages.append(arg)
            elif isinstance(arg, list):
                for item in arg:
                    if isinstance(item,Passage): self.passages.append(item)
    def append(self, passage):
        """
        Append single Passage object to collection.
        """
        if isinstance(passage, Passage): self.passages.append(passage)
    def sort(self):
        """
        Sort Passage objects in collection based on default sorting order
        """
        return self.passages.sort()
    def reference_string(self, abbreviated=False, dash="-"):
        """
        x.reference_string() <==> str(x)
        Return string representation of PassageCollection. Primarily for internal usage.
        """
        #First checking easy options.
        if len(self.passages) == 0: return ""
        if len(self.passages) == 1: return str(self.passages[0])
        #Filtering out any invalid passages
        passagelist = [p for p in self.passages if p.is_valid()]
        if len(passagelist) == 0: return ""
        #Group by consecutive passages with same book
        groups = []; i=0;
        while i < len(passagelist):
            group_start = i; book = passagelist[i].book_n
            while i+1 < len(passagelist) and passagelist[i+1].book_n == book:
                i += 1
            group_end = i
            groups.append(passagelist[group_start:group_end+1])
            i += 1
        #Create strings for each group (of consecutive passages within the same book)
        group_strings = [];
        for group in groups:
            #Treat single-chapter books differently
            if group[0].bd.number_chapters[group[0].book_n] == 1:
                parts = []
                for p in group:
                    if p.start_verse == p.end_verse:
                        parts.append(str(p.start_verse))
                    else:
                        parts.append(str(p.start_verse) + dash + str(p.end_verse))
                group_strings.append(group[0].book_name(abbreviated) + " " + ", ".join(parts))
            else:
                #Multi-chapter-book group
                if (len(group) == 1 and group[0].complete_book() == 1.0):
                    #Special case where there is only one reference in bunch, and that reference is for a whole book.
                    group_strings.append(group[0].book_name(abbreviated))
                else:
                    #For readability and simplicity, this part of the algorithm is within the GroupBunch class
                    bunched = GroupBunch()
                    for p in group: bunched.add(p)
                    group_strings.append(bunched.reference_string(abbreviated, dash))
        return "; ".join(group_strings)
    def __str__(self):
        """
        x.__str__() <==> str(x)
        Return passage string
        """
        return self.reference_string()
    def __unicode__(self):
        """
        x.__unicode__() <==> unicode(x)
        Return unicode version of passage string. Uses en-dash for ranges.
        """
        return unicode(self.reference_string(dash=u"–"))
    def abbr(self):
        """
        Return abbreviated passage string
        """
        return self.reference_string(abbreviated=True)
    def uabbr(self):
        """
        Return unicode-type abbreviated passage string. Uses en-dash for ranges.
        """
        return unicode(self.reference_string(abbreviated=True, dash=u"–"))
    def __repr__(self):
        """
        x.__repr__() <==> x
        """
        return "PassageCollection(" + ", ".join([repr(x) for x in self.passages]) + ")"
    def __add__(self,other):
        """
        x.__add__(y) <==> x + y
        """
        if isinstance(other,Passage):
            return PassageCollection(self.passages,other)
        elif isinstance(other,PassageCollection):
            return PassageCollection(self.passages,other.passages)
        else:
            return NotImplemented
    def __eq__(self,other):
        """
        x.__eq__(y) <==> x == y
        """
        if not isinstance(other,PassageCollection): return False
        if len(self.passages) != len(other.passages): return False
        for (a,b) in zip(self.passages,other.passages):
            if a != b: return False
        return True
    def __ne__(self,other):
        """
        x.__ne__(y) <==> x != y
        """
        return not self.__eq__(other)


class GroupBunch:
    """
    Internal-use class for creating strings for 'bunches' of passages that are in the same book, and where that book is a multi-chapter book.
    """
    def __init__(self):
        self.bunches = defaultdict(lambda: []) #lists of reference objects, indexed by order
        self.full_chapter_bunch = defaultdict(lambda: False)
        self.order = 0
        self.last_full_chapter_loc = -1 #order
        self.last_partial_chapter = [None, -1] #[chapter, order]
    def add(self,reference):
        if self.order == 0:
            self.book_n = reference.book_n
        if reference.complete_chapter():
            #Reference is a full chapter length
            if self.last_full_chapter_loc >= 0:
                #Last reference was a full chapter, so add it to previous bunch
                self.bunches[self.last_full_chapter_loc].append(reference)
            else:
                self.bunches[self.order].append(reference)
                self.last_full_chapter_loc = self.order
                self.full_chapter_bunch[self.order] = True
            self.last_partial_chapter = [None, -1]
        else:
            if reference.start_chapter == reference.end_chapter:
                #Some verse range that is within the same chapter
                if reference.start_chapter == self.last_partial_chapter[0]:
                    #Same chapter as for last passage, so add to previous bunch
                    self.bunches[self.last_partial_chapter[1]].append(reference)
                else:
                    #Different to last passage
                    self.bunches[self.order].append(reference)
                    self.last_partial_chapter = [reference.start_chapter, self.order]
            else:
                #Verse range over two or more chapters, between arbitrary verses (e.g. 5:2-7:28)
                self.last_partial_chapter = [None, -1]
                self.bunches[self.order].append(reference)
            self.last_full_chapter_loc = -1
        self.order += 1
    def reference_string(self, abbreviated, dash):
        if self.order == 0:
            #No passages have been added to bunch; return blank.
            return ""
        #Get passage bunches and order them
        ordered_bunches = sorted(self.bunches.items(), cmp=lambda x,y: cmp(x[0], y[0]) )
        #Internal function
        def full_ch_ref(reference):
            if reference.start_chapter == reference.end_chapter:
                return str(reference.start_chapter)
            else:
                return str(reference.start_chapter) + dash + str(reference.end_chapter)
        def verses_only(reference):
            if reference.start_verse == reference.end_verse:
                return str(reference.start_verse)
            else:
                return str(reference.start_verse) + dash + str(reference.end_verse)
        #Now iterate through bunches, creating their textual representations
        textual_bunches = []
        for order, bunch in ordered_bunches:
            if self.full_chapter_bunch[order]:
                if order == 0:
                    textual_bunches.append(", ".join([full_ch_ref(x) for x in bunch]))
                elif len(bunch) == 1:
                    textual_bunches.append("ch. " + full_ch_ref(bunch[0]))
                else:
                    textual_bunches.append("chs. " + ", ".join([full_ch_ref(x) for x in bunch]))
            else:
                #Not a full-chapter bunch.
                if len(bunch) == 1:
                    #NB: this bunch may be over two or more chapters
                    if bunch[0].start_chapter == bunch[0].end_chapter:
                        textual_bunches.append(str(bunch[0].start_chapter) + ":" + verses_only(bunch[0]))
                    else:
                        textual_bunches.append(str(bunch[0].start_chapter) + ":" + str(bunch[0].start_verse) + dash + str(bunch[0].end_chapter) + ":" + str(bunch[0].end_verse))
                    pass
                else:
                    #Guaranteed (via self.add() algorithm) to be within same chapter
                    textual_bunches.append(str(bunch[0].start_chapter) + " vv. " + ", ".join([verses_only(x) for x in bunch]))
        if abbreviated:
            book = bibledata.book_names[self.book_n][2]
        else:
            book = bibledata.book_names[self.book_n][1]
        return book + " " + ", ".join(textual_bunches)


class InvalidPassageException(Exception):
    pass


def get_passage_text(*args, **kwargs):
    translation = kwargs.get(translation,"ESV")
    return bible_data(translation).get_passage_text()


def bible_data(translation):
    """ Private method to return bible-data module corresponding to given translation """
    if translation == "ESV":
        return bibledata.esv
    else:
        return bibledata.esv


if __name__ == "__main__":
    import doctest
    doctest.testmod()