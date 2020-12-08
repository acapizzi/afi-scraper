
dictlist = [
    {'something':1},
    {'smomething':2},
    {},
    {'something':54,'test':True,'empty':''}
]

print(dictlist)
dictlist = list(filter(None,dictlist))
print(dictlist)