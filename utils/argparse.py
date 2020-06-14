"""
The MIT License (MIT)

Copyright (c) 2019 IAmTomahawkx

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.

"""

class Adapter:
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            self = object.__new__(cls)
            cls._instance = self

        return cls._instance

    def __init__(self, brackets=(('(', ')'),), delimiters=(',',)):
        self._original_brackets = brackets
        self._brackets = dict(brackets)
        self.brackets_in = set([b[0] for b in brackets])
        self.brackets_out = set([b[1] for b in brackets])
        self.delimiters = set(delimiters)
    
    def parse(self, buffer, maxdepth=0):
        return self._actual_parse(buffer, 0, maxdepth)
    
    def _actual_parse(self, buffer, depth, maxdepth):
        collecting = False
        params = [""] # we start with an empty string so we can add anything before a parameter.
        # if there are no parameters, we will just return the string, which is essentially returning the buffer
        bracketlvl = 0
        for index, char in enumerate(buffer):
            if isinstance(params[-1], dict):
                params[-1]['raw'] += char

            if char == "$" and bracketlvl == 0:
                # i need to do a lookahead here to check if the parameter has arguments.
                # i can check this by looking for brackets. if the first character that isnt alphanumerical isnt a bracket,
                # we can pretty safely assume theres no arguments.
                # if it doesnt have brackets, we will simply add it to the current argument (as a new one hasnt been created at this point.)
                brack = False
                for c in buffer[index+1:]:
                    if not c.isalnum():
                        if c in self.brackets_in:
                            brack = True
                        break
                    del c # keep things tidy
                if not brack:
                    # there are no brackets, just append and go to the next iteration
                    del brack
                    if isinstance(params[-1], dict):
                        params[-1]['params'][-1] += char
                    else:
                        params[-1] += char
                    continue

                # if i'm here, there are brackets (and therfor arguments), so create a new 'param' dict
                del brack
                params.append({"name": "", "params": [""], "raw": "$"})
                collecting = True # enable name collection
                continue
            
            if char in self.brackets_in and buffer[index-1]!="\\":
                # this is to stop param name collection.
                # buffer[index-1]!="\\" - this is done to allow escaping of the brackets and delimiters. essentially, doing $hi\() will break the program.
                # so dont do that.
                collecting = False
                bracketlvl += 1 # up the bracket depth. i could figure out a way to do this all in one go,
                # but that would get very complex very fast (i tried, it didnt go well)
                # instead, we will simply run this function again, and pass each argument as a buffer.
                # keeping track of the bracket levels allows me to only have one level of parsing, and ignore any params inside the argument im parsing.
                if bracketlvl <= 1: # if its smaller than one, we need to remove it so it doesnt appear in the first argument.
                    continue
            
            if collecting:
                # we are collecting a parameter name here, so append to the name, and go to the next iteration.
                # this is purposefully put after the bracket_in check, so it doesnt eat the entire buffer.
                params[-1]['name'] += char
                continue
            
            if char in self.brackets_out and buffer[index-1]!="\\":
                # this indicates that i might be done parsing arguments. but the possibility remains of it being for an argument inside what im parsing,
                # so i'll remove a bracket depth, and check if thats the last one.
                bracketlvl = max(bracketlvl-1, 0) # and yes, i could just do -= 1, but this way allows me to bottom out at 0, and not go into negatives.
                if bracketlvl == 0:
                    if isinstance(params[-1], dict):
                        if not params[-1]['params'][-1].strip():
                            params[-1]['params'].pop()
                    params.append("")
                    continue # if it is, im going to continue, as to not add the bracket to the outer layer.
            
            if char in self.delimiters and bracketlvl <= 1 and buffer[index-1]!="\\":
                # if we are here, this means that weve hit a delimiter.
                params[-1]['params'][-1] = params[-1]['params'][-1].strip() # first, remove any lingering whitespace from the current argument
                params[-1]['params'].append("") # create a new argument.
                continue
            
            #if i've hit this point, that means there is nothing special about the character, so add it to the current argument
            if isinstance(params[-1], dict):
                # if its a dict, it must be a parameter, so add it to the last argument (last argument up to this point that is)
                params[-1]['params'][-1] += char
            else:
                # this one aint rocket science. add it to the last argument.
                params[-1] += char
        
        for item in params:
            # now were going to parse each argument
            if isinstance(item, dict) and not (depth+1 >= maxdepth):
                for index, param in enumerate(item['params']):
                    item['params'][index] = self._actual_parse(param, depth+1, maxdepth)

        if depth == 0:
            return params
        
        if len(params) == 1:
            return params[0]
            
        return params

    def copy(self):
        return Adapter(self._original_brackets, self.delimiters)


def split(string: str):
    ret = ['']
    collect = False
    for char in string:
        if char == "-" and ret[-1] != "-":
            collect = True
            ret.append("-")
            continue
        if char.isspace() and collect:
            collect = False
            ret.append("")
            continue
        ret[-1]+=char
    # noinspection PyBroadException
    try: ret.remove("")
    except: pass
    return ret
