# 
# copyright ###################################################################
# This file is part of the Xtrack Package.
# Copyright (c) CERN, 2020.
# #############################################################################
import os



copyright_statement = """
copyright ###################################################################
This file is part of the Xtrack Package.
Copyright (c) CERN, 2020.
#############################################################################"""

config = [
    {'extension': '.py', 'comment_char': '#'},
    {'extension': '.h', 'comment_char': '//'},
]

for cc in config:
    extension =  cc['extension']
    comment_char = cc['comment_char']

    cpright_lines = [comment_char + ' ' + line
                        for line in copyright_statement.splitlines()]

    for root, dirs, files in os.walk("./"):
        for fname in files:
            if fname.endswith(extension):
                file = os.path.join(root, file)
                print(file)
                with open(file, 'r') as fid:
                    lines = fid.readlines()
                # Remove copyright statement if present
                if lines[0].startswith(comment_char + ' ' + 'copyright ##'):
                    for ill, ll in lines:
                        assert ll.startswith(comment_char)
                        if ll.startswith(comment_char + ' ' + '########'):
                            end_cpright = ill + 1
                            break
                    lines = lines[end_cpright:]

                lines = cpright_lines + lines

                with open(file, 'w') as fid:
                    fid.writelines(lines)