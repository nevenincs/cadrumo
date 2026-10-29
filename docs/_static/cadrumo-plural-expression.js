/* Cadrumo plural-form evaluator for the Sphinx interface strings.
 *
 * Loaded only by the desktop documentation flavor, after Sphinx's doctools.js
 * and before the language's translations.js. The desktop application serves
 * each page under a script policy that refuses to turn a string into code, and
 * doctools.js builds its plural-form function from the catalog's gettext
 * expression with `new Function`, which that policy rejects with an EvalError
 * on every page of a translated site. This script replaces only the one
 * function that does it, `Documentation.addTranslations`, with an evaluator of
 * the gettext expression language that builds no code from the string.
 *
 * Supported: the integer variable `n`, decimal literals, parentheses, and the
 * C operators gettext plural expressions use: `?:`, `||`, `&&`, `== !=`,
 * `< > <= >=`, `+ -`, `* / %`, and unary `! -`. As in C, a comparison or logical
 * operator yields 0 or 1, so the result always indexes the catalog's list of
 * plural forms. An expression outside that language is refused when the
 * catalog loads, naming the expression, rather than evaluated some other way.
 * `/` truncates toward zero, as C integer division does. */
(function () {
  "use strict";

  /* doctools.js declares Documentation with `const`, so it is a global binding
   * shared by classic scripts but not a property of window. */
  if (typeof Documentation === "undefined") return;

  var TOKEN = /\s*(?:(\d+)|(n)|(\|\||&&|==|!=|<=|>=|[-+*/%<>!?:()]))/y;

  function tokenize(source) {
    var tokens = [];
    var position = 0;
    var text = String(source);
    while (position < text.length) {
      TOKEN.lastIndex = position;
      var match = TOKEN.exec(text);
      if (!match) {
        if (/^\s*$/.test(text.slice(position))) break;
        throw new Error("unsupported plural expression: " + text);
      }
      position = TOKEN.lastIndex;
      if (match[1] !== undefined) tokens.push({ number: Number(match[1]) });
      else if (match[2] !== undefined) tokens.push({ variable: true });
      else tokens.push({ operator: match[3] });
    }
    return tokens;
  }

  var BINARY = [
    ["||"],
    ["&&"],
    ["==", "!="],
    ["<", ">", "<=", ">="],
    ["+", "-"],
    ["*", "/", "%"],
  ];

  var APPLY = {
    "||": function (a, b) { return a || b ? 1 : 0; },
    "&&": function (a, b) { return a && b ? 1 : 0; },
    "==": function (a, b) { return a === b ? 1 : 0; },
    "!=": function (a, b) { return a !== b ? 1 : 0; },
    "<": function (a, b) { return a < b ? 1 : 0; },
    ">": function (a, b) { return a > b ? 1 : 0; },
    "<=": function (a, b) { return a <= b ? 1 : 0; },
    ">=": function (a, b) { return a >= b ? 1 : 0; },
    "+": function (a, b) { return a + b; },
    "-": function (a, b) { return a - b; },
    "*": function (a, b) { return a * b; },
    "/": function (a, b) { return Math.trunc(a / b); },
    "%": function (a, b) { return a % b; },
  };

  function parse(source) {
    var tokens = tokenize(source);
    var index = 0;

    function peek() { return tokens[index]; }
    function isOperator(token, symbols) {
      return token !== undefined && token.operator !== undefined && symbols.indexOf(token.operator) !== -1;
    }
    function expect(symbol) {
      if (!isOperator(peek(), [symbol])) throw new Error("unsupported plural expression: " + source);
      index += 1;
    }

    function conditional() {
      var test = binary(0);
      if (!isOperator(peek(), ["?"])) return test;
      index += 1;
      var consequent = conditional();
      expect(":");
      var alternate = conditional();
      return function (n) { return test(n) ? consequent(n) : alternate(n); };
    }

    function binary(level) {
      if (level === BINARY.length) return unary();
      var left = binary(level + 1);
      while (isOperator(peek(), BINARY[level])) {
        var apply = APPLY[peek().operator];
        index += 1;
        left = combine(apply, left, binary(level + 1));
      }
      return left;
    }

    function combine(apply, left, right) {
      return function (n) { return apply(left(n), right(n)); };
    }

    function unary() {
      if (isOperator(peek(), ["!"])) {
        index += 1;
        var operand = unary();
        return function (n) { return operand(n) ? 0 : 1; };
      }
      if (isOperator(peek(), ["-"])) {
        index += 1;
        var negated = unary();
        return function (n) { return -negated(n); };
      }
      return primary();
    }

    function primary() {
      var token = peek();
      if (token === undefined) throw new Error("unsupported plural expression: " + source);
      index += 1;
      if (token.number !== undefined) return function () { return token.number; };
      if (token.variable) return function (n) { return n; };
      if (token.operator === "(") {
        var inner = conditional();
        expect(")");
        return inner;
      }
      throw new Error("unsupported plural expression: " + source);
    }

    var expression = conditional();
    if (index !== tokens.length) throw new Error("unsupported plural expression: " + source);
    return expression;
  }

  Documentation.addTranslations = function (catalog) {
    Object.assign(Documentation.TRANSLATIONS, catalog.messages);
    Documentation.PLURAL_EXPR = parse(catalog.plural_expr);
    Documentation.LOCALE = catalog.locale;
  };
})();
