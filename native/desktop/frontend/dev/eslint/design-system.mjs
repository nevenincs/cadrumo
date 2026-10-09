import { basename } from "node:path";

const literalScale =
  /\[[^\]]*(?:\d+(?:\.\d+)?(?:px|rem|em|ms|s)(?=[^a-z0-9]|$)|#[\da-f]{3,8}\b|(?:rgb|hsl|oklch)\()[^\]]*\]/i;
const defaultColor =
  /\b(?:bg|text|border|ring|outline|fill|stroke|decoration|shadow)-(?:black|white|(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d+)\b/;
const independentScale = /\b(?:z|duration|delay)-\d+\b/;
const styleLiteral =
  /(?:\d+(?:\.\d+)?(?:px|rem|em|ms|s)(?=[^a-z0-9]|$)|#[\da-f]{3,8}\b|(?:rgb|hsl|oklch)\()/i;
const dimensionalProperty =
  /^(?:width|height|minWidth|maxWidth|minHeight|maxHeight|fontSize|lineHeight|letterSpacing|borderWidth|borderRadius|padding(?:Top|Right|Bottom|Left)?|margin(?:Top|Right|Bottom|Left)?|gap|rowGap|columnGap|zIndex|transitionDuration|animationDuration)$/;
const colorProperty =
  /^(?:color|background|backgroundColor|borderColor|outlineColor|fill|stroke)$/;
const contextualColor =
  /^(?:var\(|transparent$|currentColor$|inherit$|Canvas(?:Text)?$|Highlight(?:Text)?$|Button(?:Text|Face|Border)?$)/;

/** Product components and stories share the same token ownership. */
const tokenStyles = {
  meta: {
    type: "problem",
    schema: [],
    messages: {
      token:
        "Use a semantic token, token-backed utility or computed argument instead of a literal style scale.",
    },
  },
  create(context) {
    function check(node, value) {
      if (
        literalScale.test(value) ||
        defaultColor.test(value) ||
        independentScale.test(value)
      )
        context.report({ node, messageId: "token" });
    }
    return {
      Literal(node) {
        if (typeof node.value === "string") check(node, node.value);
      },
      TemplateElement(node) {
        check(node, node.value.cooked ?? node.value.raw);
      },
      Property(node) {
        if (node.computed || node.value.type !== "Literal") return;
        const inStyle = context.sourceCode
          .getAncestors(node)
          .some(
            (parent) =>
              (parent.type === "JSXAttribute" &&
                parent.name.name === "style") ||
              (parent.type === "VariableDeclarator" &&
                parent.id.type === "Identifier" &&
                /styles?$/i.test(parent.id.name)),
          );
        if (!inStyle) return;
        const key =
          node.key.type === "Identifier" ? node.key.name : node.key.value;
        if (typeof key !== "string") return;
        const value = node.value.value;
        if (
          (dimensionalProperty.test(key) &&
            ((typeof value === "number" &&
              value !== 0 &&
              key !== "lineHeight") ||
              (typeof value === "string" && styleLiteral.test(value)))) ||
          (colorProperty.test(key) &&
            typeof value === "string" &&
            !contextualColor.test(value))
        )
          context.report({ node: node.value, messageId: "token" });
      },
    };
  },
};

const componentNames = {
  meta: {
    type: "problem",
    schema: [],
    messages: {
      component:
        "Name product React component files in PascalCase and primitives in kebab-case; colocate stories with their component.",
    },
  },
  create(context) {
    return {
      Program(node) {
        const file = context.filename.replaceAll("\\", "/");
        if (!file.endsWith(".tsx") || !file.includes("/src/")) return;
        const name = basename(file);
        if (name === "main.tsx") return;
        const primitive = file.includes("/components/ui/");
        const pattern = primitive
          ? /^[a-z]+(?:-[a-z]+)*(?:\.stories)?\.tsx$/
          : /^[A-Z][A-Za-z0-9]*(?:\.stories)?\.tsx$/;
        if (!pattern.test(name))
          context.report({ node, messageId: "component" });
      },
    };
  },
};

export default {
  rules: { "token-styles": tokenStyles, "component-names": componentNames },
};
