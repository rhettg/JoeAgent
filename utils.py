import sys, imp, os, string

def load_class(class_name):
    ndx = class_name.find(".")    
    path = None
    module = None
    while ndx >= 0:
        module_name = class_name[:ndx]
        class_name = class_name[ndx+1:]
        try:
            module = sys.modules[module_name]
        except KeyError:
            if module != None:
                path = module.__path__

            #print "Module: %s Class: %s Path: %s" % (module_name, class_name, path)

            (file, filename, description) = imp.find_module(module_name, path)
            module = imp.load_module(module_name, file, filename, description)
        ndx = class_name.find(".")

    instance = module.__dict__[class_name]
    return instance

def split_class_name(class_name):
    """Return a tuple of module name and class name"""
    ndx = class_name.rfind(".")
    return (class_name[:ndx], class_name[ndx+1:])

def get_class(class_name):
    module_name, class_name = split_class_name(class_name)
                                                                    
    try:
        mod = sys.modules[module_name]
    except KeyError:
        mod = __import__(module_name)
        for comp in string.split(module_name, '.')[1:]:
            mod = getattr(mod, comp)
        sys.modules[module_name] = mod
                                                                    
    return mod.__dict__[class_name]

def get_single(list):
    if len(list) > 0:
        return list[0]
    else:
        return None
