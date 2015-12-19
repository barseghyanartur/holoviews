"""
HoloViews can be used to build highly-nested data-structures
containing large amounts of raw data. As a result, it is difficult to
generate a readable representation that is both informative yet
concise.

As a result, HoloViews does not attempt to build representations that
can be evaluated with eval; such representations would typically be
far too large to be practical. Instead, all HoloViews objects can be
represented as tree structures, showing how to access and index into
your data.

In addition, there are several different ways of
"""

import re
import param
# IPython not required to import ParamPager
from param.ipython import ParamPager
from holoviews.core.util import sanitize_identifier, group_sanitizer, label_sanitizer



class ParamFilter(param.ParameterizedFunction):
    """
    Given a parameterized object, return a proxy parameterized object
    holding only the parameters that match some filter criterion.

    A filter is supplied with the parameter name and the parameter
    object and must return a boolean. A regular expression filter has
    been supplied and may be used to search for parameters mentioning
    'bounds' as follows:

    filtered = ParamFilter(obj, ParamFilter.regexp_filter('bounds'))

    This may be used to filter documentation generated by param.
    """

    def __call__(self, obj, filter_fn=None):
        if filter_fn is None:
            return obj

        name = obj.__name__ if isinstance(obj,type) else obj.__class__.__name__
        class_proxy = type(name, (param.Parameterized,),
                      {k:v for k,v in obj.params().items() if filter_fn(k,v)})

        if isinstance(obj,type):
            return class_proxy
        else:
            instance_params = obj.get_param_values()
            obj_proxy = class_proxy()
            filtered = {k:v for k,v in instance_params
                        if (k in obj_proxy.params())
                            and not obj_proxy.params(k).constant}
            obj_proxy.set_param(**filtered)
            return obj_proxy

    @param.parameterized.bothmethod
    def regexp_filter(self_or_cls, pattern):
        """
        Builds a parameter filter using the supplied pattern (may be a
        general Python regular expression)
        """
        def inner_filter(name, p):
            name_match = re.search(pattern,name)
            if name_match is not None:
                return True
            doc_match = re.search(pattern,p.doc)
            if doc_match is not None:
                return True
            return False
        return inner_filter


class InfoPrinter(object):
    """
    Class for printing other information related to an object that is
    of use to the user.
    """
    headings = ['\x1b[1;35m%s\x1b[0m', '\x1b[1;32m%s\x1b[0m']
    ansi_escape = re.compile(r'\x1b[^m]*m')
    ppager = ParamPager()
    store = None

    @classmethod
    def get_parameter_info(cls, obj, ansi=False,  show_values=True,
                           pattern=None, max_col_len=40):
        """
        Get parameter information from the supplied class or object.
        """
        if cls.ppager is None: return ''
        if pattern is not None:
            obj = ParamFilter(obj, ParamFilter.regexp_filter(pattern))
            if len(obj.params()) <=1:
                return None
        param_info = cls.ppager.get_param_info(obj)
        param_list = cls.ppager.param_docstrings(param_info)
        if not show_values:
            retval = cls.ansi_escape.sub('', param_list) if not ansi else param_list
            return cls.highlight(pattern, retval)
        else:
            info = cls.ppager(obj)
            if ansi is False:
                info = cls.ansi_escape.sub('', info)
            return cls.highlight(pattern, info)

    @classmethod
    def heading(cls, heading_text, char='=', level=0, ansi=False):
        """
        Turn the supplied heading text into a suitable heading with
        optional underline and color.
        """
        heading_color = cls.headings[level] if ansi else '%s'
        if char is None:
            return heading_color % '%s\n' % heading_text
        else:
            heading_ul = char*len(heading_text)
            return heading_color % '%s\n%s\n%s' % (heading_ul, heading_text, heading_ul)


    @classmethod
    def highlight(cls, pattern, string):
        if pattern is None: return string
        return re.sub(pattern, '\033[43;1;30m\g<0>\x1b[0m',
                      string, flags=re.IGNORECASE)


    @classmethod
    def info(cls, obj, ansi=False, backend='matplotlib', visualization=True, pattern=None):
        """
        Show information about an object in the given category. ANSI
        color codes may be enabled or disabled.
        """
        ansi_escape = re.compile(r'\x1b[^m]*m')

        isclass = isinstance(obj, type)
        name = obj.__name__ if isclass  else obj.__class__.__name__
        plot_class = cls.store.registry[backend].get(obj if isclass else type(obj), None)
        # Special case to handle PlotSelectors
        if hasattr(plot_class, 'plot_classes'):
            plot_class = plot_class.plot_classes.values()[0]


        if visualization is False or plot_class is None:
            if pattern is not None:
                obj = ParamFilter(obj, ParamFilter.regexp_filter(pattern))
                if len(obj.params()) <=1:
                    return ('No %r parameters found matching pattern %r'
                            % (name, pattern))
            info = param.ipython.ParamPager()(obj)
            if ansi is False:
                info = ansi_escape.sub('', info)
            return cls.highlight(pattern, info)

        heading = name if isclass else '{name}: {group} {label}'.format(name=name,
                                                                        group=obj.group,
                                                                        label=obj.label)
        prefix = heading
        lines = [prefix, cls.object_info(obj, name, ansi=ansi)]

        if not isclass:
            lines += ['', cls.target_info(obj, ansi=ansi)]
        if plot_class is not None:
            lines += ['', cls.options_info(plot_class, ansi, pattern=pattern)]
        return "\n".join(lines)


    @classmethod
    def get_target(cls, obj):
        objtype=obj.__class__.__name__
        group = group_sanitizer(obj.group)
        label = ('.' + label_sanitizer(obj.label) if obj.label else '')
        target = '{objtype}.{group}{label}'.format(objtype=objtype,
                                                   group=group,
                                                   label=label)
        return (None, target) if hasattr(obj, 'values') else (target, None)


    @classmethod
    def target_info(cls, obj, ansi=False):
        if isinstance(obj, type): return ''

        targets = obj.traverse(cls.get_target)
        elements, containers = zip(*targets)
        element_set = set(el for el in elements if el is not None)
        container_set = set(c for c in containers if c is not None)

        element_info = None
        if len(element_set) == 1:
            element_info = 'Element: %s'  % list(element_set)[0]
        elif len(element_set) > 1:
            element_info = 'Elements:\n   %s'  % '\n   '.join(sorted(element_set))

        container_info = None
        if len(container_set) == 1:
            container_info = 'Container: %s'  % list(container_set)[0]
        elif len(container_set) > 1:
            container_info = 'Containers:\n   %s'  % '\n   '.join(sorted(container_set))
        heading = cls.heading('Target Specifications', ansi=ansi, char="-")

        target_header = '\nTargets in this object available for customization:\n'
        if element_info and container_info:
            target_info = '%s\n\n%s' % (element_info, container_info)
        else:
            target_info = element_info if element_info else container_info

        target_footer = ("\nTo see the options info for one of these target specifications,"
                         "\nwhich are of the form {type}[.{group}[.{label}]], do holoviews.help({type}).")

        return '\n'.join([heading, target_header, target_info, target_footer])


    @classmethod
    def object_info(cls, obj, name, ansi=False):
        element = not getattr(obj, '_deep_indexable', False)
        url = ('https://ioam.github.io/holoviews/Tutorials/Elements.html#{obj}'
               if element else 'https://ioam.github.io/holoviews/Tutorials/Containers.html#{obj}')
        link = url.format(obj=name)

        msg = ("\nOnline example: {link}"
               + "\nHelp for the data object: holoviews.help({obj})"
               + " or holoviews.help(<{lower}_instance>)")

        return '\n'.join([msg.format(obj=name,
                                     lower=name.lower(),
                                     link=link)])


    @classmethod
    def options_info(cls, plot_class, ansi=False, pattern=None):
        if plot_class.style_opts:
            backend_name = plot_class.renderer.backend
            style_info = ("\n(Consult %s's documentation for more information.)" % backend_name)
            style_keywords = '\t%s' % ', '.join(plot_class.style_opts)
            style_msg = '%s\n%s' % (style_keywords, style_info)
        else:
            style_msg = '\t<No style options available>'

        param_info = cls.get_parameter_info(plot_class, ansi=ansi, pattern=pattern)
        lines = [ cls.heading('Style Options', ansi=ansi, char="-"), '',
                  style_msg, '',
                  cls.heading('Plot Options', ansi=ansi, char="-"), '']
        if param_info is not None:
            lines += ["The plot options are the parameters of the plotting class:\n",
                      param_info]
        elif pattern is not None:
            lines+= ['No %r parameters found matching pattern %r.'
                     % (plot_class.__name__, pattern)]
        else:
            lines+= ['No %r parameters found.' % plot_class.__name__]

        return '\n'.join(lines)


class PrettyPrinter(object):
    """
    The PrettyPrinter used to print all HoloView objects via the
    pprint classmethod.
    """

    tab = '   '

    type_formatter= ':{type}'

    @classmethod
    def pprint(cls, node):
        return  cls.serialize(cls.recurse(node))

    @classmethod
    def serialize(cls, lines):
        accumulator = []
        for level, line in lines:
            accumulator.append((level *cls.tab) + line)
        return "\n".join(accumulator)

    @classmethod
    def shift(cls, lines, shift=0):
        return [(lvl+shift, line) for (lvl, line) in lines]

    @classmethod
    def padding(cls, items):
        return max(len(p) for p in items) if len(items) > 1 else len(items[0])

    @classmethod
    def component_type(cls, node):
        "Return the type.group.label dotted information"
        if node is None: return ''
        return cls.type_formatter.format(type=str(type(node).__name__))

    @classmethod
    def recurse(cls, node, attrpath=None, attrpaths=[], siblings=[], level=0, value_dims=True):
        """
        Recursive function that builds up an ASCII tree given an
        AttrTree node.
        """
        level, lines = cls.node_info(node, attrpath, attrpaths, siblings, level, value_dims)
        attrpaths = ['.'.join(k) for k in node.keys()] if  hasattr(node, 'children') else []
        siblings = [node.get(child) for child in attrpaths]
        for index, attrpath in enumerate(attrpaths):
            lines += cls.recurse(node.get(attrpath), attrpath, attrpaths=attrpaths,
                                 siblings=siblings, level=level+1, value_dims=value_dims)
        return lines

    @classmethod
    def node_info(cls, node, attrpath, attrpaths, siblings, level, value_dims):
        """
        Given a node, return relevant information.
        """
        if hasattr(node, 'children'):
            (lvl, lines) = (level, [(level, cls.component_type(node))])
        elif hasattr(node, 'main'):
            (lvl, lines) = cls.adjointlayout_info(node, siblings, level, value_dims)
        elif getattr(node, '_deep_indexable', False):
            (lvl, lines) = cls.ndmapping_info(node, siblings, level, value_dims)
        else:
            (lvl, lines) = cls.element_info(node, siblings, level, value_dims)

        # The attribute indexing path acts as a prefix (if applicable)
        if attrpath is not None:
            padding = cls.padding(attrpaths)
            (fst_lvl, fst_line) = lines[0]
            lines[0] = (fst_lvl, '.'+attrpath.ljust(padding) +' ' + fst_line)
        return (lvl, lines)


    @classmethod
    def element_info(cls, node, siblings, level, value_dims):
        """
        Return the information summary for an Element. This consists
        of the dotted name followed by an value dimension names.
        """
        info =  cls.component_type(node)
        if siblings:
            padding = cls.padding([cls.component_type(el) for el in siblings])
            info.ljust(padding)
        if len(node.kdims) >= 1:
            info += cls.tab + '[%s]' % ','.join(d.name for d in node.kdims)
        if value_dims and len(node.vdims) >= 1:
            info += cls.tab + '(%s)' % ','.join(d.name for d in node.vdims)
        return level, [(level, info)]


    @classmethod
    def adjointlayout_info(cls, node, siblings, level, value_dims):
        first_line = cls.component_type(node)
        lines = [(level, first_line)]
        additional_lines = []
        for component in list(node.data.values()):
            additional_lines += cls.recurse(component, level=level)
        lines += cls.shift(additional_lines, 1)
        return level, lines


    @classmethod
    def ndmapping_info(cls, node, siblings, level, value_dims):

        key_dim_info = '[%s]' % ','.join(d.name for d in node.kdims)
        first_line = cls.component_type(node) + cls.tab + key_dim_info
        lines = [(level, first_line)]

        additional_lines = []
        if len(node.data) == 0:
            return level, lines
        # .last has different semantics for GridSpace
        last = list(node.data.values())[-1]
        if hasattr(last, 'children'):
            additional_lines = cls.recurse(last, level=level)
        # NdOverlays, GridSpace, Ndlayouts
        elif last is not None and getattr(last, '_deep_indexable'):
            level, additional_lines = cls.ndmapping_info(last, [], level, value_dims)
        else:
            _, additional_lines = cls.element_info(last, siblings, level, value_dims)
        lines += cls.shift(additional_lines, 1)
        return level, lines


__all__ = ['PrettyPrinter', 'InfoPrinter']
