class UIComponent:
    """Represents a UI component in the AST."""
    def __init__(self, name, props=None, children=None):
        self.name = name
        self.props = props or {}
        self.children = children or []

    def to_dict(self):
        return {
            "name": self.name,
            "props": self.props,
            "children": [c.to_dict() for c in self.children]
        }


class UIAST:
    """Represents the Abstract Syntax Tree of a UI Page."""
    def __init__(self):
        self.root = UIComponent("Page")

    def add_component(self, component):
        self.root.children.append(component)

    def to_json(self):
        return self.root.to_dict()
