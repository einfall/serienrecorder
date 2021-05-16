/*!
 * Poppers v0.1.2
 * Copyright (c) 2018-present Boring <boring@boring.wang> (https://boring.wang/)
 * MIT license
 */
'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

require('core-js/modules/es6.object.assign');
require('core-js/modules/es6.function.name');
require('core-js/modules/es6.array.iterator');
require('core-js/modules/es6.object.keys');
require('core-js/modules/web.dom.iterable');
require('core-js/modules/es6.regexp.to-string');
require('core-js/modules/es6.regexp.split');
require('core-js/modules/es6.promise');
require('dom4');

function _classCallCheck(instance, Constructor) {
  if (!(instance instanceof Constructor)) {
    throw new TypeError("Cannot call a class as a function");
  }
}

function _defineProperties(target, props) {
  for (var i = 0; i < props.length; i++) {
    var descriptor = props[i];
    descriptor.enumerable = descriptor.enumerable || false;
    descriptor.configurable = true;
    if ("value" in descriptor) descriptor.writable = true;
    Object.defineProperty(target, descriptor.key, descriptor);
  }
}

function _createClass(Constructor, protoProps, staticProps) {
  if (protoProps) _defineProperties(Constructor.prototype, protoProps);
  if (staticProps) _defineProperties(Constructor, staticProps);
  return Constructor;
}

function _defineProperty(obj, key, value) {
  if (key in obj) {
    Object.defineProperty(obj, key, {
      value: value,
      enumerable: true,
      configurable: true,
      writable: true
    });
  } else {
    obj[key] = value;
  }

  return obj;
}

function _objectSpread(target) {
  for (var i = 1; i < arguments.length; i++) {
    var source = arguments[i] != null ? arguments[i] : {};
    var ownKeys = Object.keys(source);

    if (typeof Object.getOwnPropertySymbols === 'function') {
      ownKeys = ownKeys.concat(Object.getOwnPropertySymbols(source).filter(function (sym) {
        return Object.getOwnPropertyDescriptor(source, sym).enumerable;
      }));
    }

    ownKeys.forEach(function (key) {
      _defineProperty(target, key, source[key]);
    });
  }

  return target;
}

function _inherits(subClass, superClass) {
  if (typeof superClass !== "function" && superClass !== null) {
    throw new TypeError("Super expression must either be null or a function");
  }

  subClass.prototype = Object.create(superClass && superClass.prototype, {
    constructor: {
      value: subClass,
      writable: true,
      configurable: true
    }
  });
  if (superClass) _setPrototypeOf(subClass, superClass);
}

function _getPrototypeOf(o) {
  _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf : function _getPrototypeOf(o) {
    return o.__proto__ || Object.getPrototypeOf(o);
  };
  return _getPrototypeOf(o);
}

function _setPrototypeOf(o, p) {
  _setPrototypeOf = Object.setPrototypeOf || function _setPrototypeOf(o, p) {
    o.__proto__ = p;
    return o;
  };

  return _setPrototypeOf(o, p);
}

function isNativeReflectConstruct() {
  if (typeof Reflect === "undefined" || !Reflect.construct) return false;
  if (Reflect.construct.sham) return false;
  if (typeof Proxy === "function") return true;

  try {
    Date.prototype.toString.call(Reflect.construct(Date, [], function () {}));
    return true;
  } catch (e) {
    return false;
  }
}

function _construct(Parent, args, Class) {
  if (isNativeReflectConstruct()) {
    _construct = Reflect.construct;
  } else {
    _construct = function _construct(Parent, args, Class) {
      var a = [null];
      a.push.apply(a, args);
      var Constructor = Function.bind.apply(Parent, a);
      var instance = new Constructor();
      if (Class) _setPrototypeOf(instance, Class.prototype);
      return instance;
    };
  }

  return _construct.apply(null, arguments);
}

function _assertThisInitialized(self) {
  if (self === void 0) {
    throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
  }

  return self;
}

function _possibleConstructorReturn(self, call) {
  if (call && (typeof call === "object" || typeof call === "function")) {
    return call;
  }

  return _assertThisInitialized(self);
}

function _superPropBase(object, property) {
  while (!Object.prototype.hasOwnProperty.call(object, property)) {
    object = _getPrototypeOf(object);
    if (object === null) break;
  }

  return object;
}

function _get(target, property, receiver) {
  if (typeof Reflect !== "undefined" && Reflect.get) {
    _get = Reflect.get;
  } else {
    _get = function _get(target, property, receiver) {
      var base = _superPropBase(target, property);

      if (!base) return;
      var desc = Object.getOwnPropertyDescriptor(base, property);

      if (desc.get) {
        return desc.get.call(receiver);
      }

      return desc.value;
    };
  }

  return _get(target, property, receiver || target);
}

function _toConsumableArray(arr) {
  return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _nonIterableSpread();
}

function _arrayWithoutHoles(arr) {
  if (Array.isArray(arr)) {
    for (var i = 0, arr2 = new Array(arr.length); i < arr.length; i++) arr2[i] = arr[i];

    return arr2;
  }
}

function _iterableToArray(iter) {
  if (Symbol.iterator in Object(iter) || Object.prototype.toString.call(iter) === "[object Arguments]") return Array.from(iter);
}

function _nonIterableSpread() {
  throw new TypeError("Invalid attempt to spread non-iterable instance");
}

/**
 * Create an Element.
 * @param {string} options.tagName
 * @param {string} options.className
 * @param {object} options.attributes
 * @param {object} options.properties
 * @param {HTMLElement[]} options.children
 * @return {HTMLElement}
 */
var createElement = function createElement() {
  var _ref = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {},
      _ref$tagName = _ref.tagName,
      tagName = _ref$tagName === void 0 ? 'div' : _ref$tagName,
      className = _ref.className,
      _ref$attributes = _ref.attributes,
      attributes = _ref$attributes === void 0 ? {} : _ref$attributes,
      properties = _ref.properties,
      _ref$children = _ref.children,
      children = _ref$children === void 0 ? [] : _ref$children;

  var element = document.createElement(tagName);

  if (className) {
    if (typeof className === 'string') {
      element.classList.add(className);
    } else if (Array.isArray(className)) {
      var _element$classList;

      (_element$classList = element.classList).add.apply(_element$classList, _toConsumableArray(className));
    }
  }

  Object.keys(attributes).forEach(function (name) {
    element.setAttribute(name, attributes[name]);
  });
  Object.assign(element, properties);
  var fragment = document.createDocumentFragment();
  children.forEach(function (child) {
    fragment.appendChild(child);
  });
  element.appendChild(fragment);
  return element;
};

var Backdrop =
/*#__PURE__*/
function () {
  function Backdrop(options) {
    _classCallCheck(this, Backdrop);

    _defineProperty(this, "_element", void 0);

    this._options = Object.assign({}, this.constructor._defaultOptions, options);
    this._element = this._createElement();
  }

  _createClass(Backdrop, [{
    key: "attach",
    value: function attach(container) {
      container.insertBefore(this._element, container.firstChild);
    }
  }, {
    key: "_createElement",
    value: function _createElement() {
      var className = [this.constructor._CLASS];

      if (this._options.transparent) {
        className.push(this.constructor._TRANSPARENT_CLASS);
      }

      var element = createElement({
        className: className
      });
      element.addEventListener('click', this._options.onClick);
      return element;
    }
  }]);

  return Backdrop;
}();

_defineProperty(Backdrop, "_defaultOptions", {
  transparent: false,
  onClick: function onClick() {
    return undefined;
  }
});

_defineProperty(Backdrop, "_CLASS", 'popper-backdrop');

_defineProperty(Backdrop, "_TRANSPARENT_CLASS", 'popper-backdrop-transparent');

var Popper =
/*#__PURE__*/
function () {
  function Popper(options) {
    _classCallCheck(this, Popper);

    _defineProperty(this, "_options", void 0);

    _defineProperty(this, "_element", void 0);

    _defineProperty(this, "_target", void 0);

    this._options = Object.assign({}, Popper._defaultOptions, this.constructor._defaultOptions, options);

    if (!this._element) {
      this._element = this._createElement();
    }

    if (this._options.target) {
      this._initTarget();
    }
  }

  _createClass(Popper, [{
    key: "pop",
    value: function pop() {
      this._attach();

      if (this._options.autoBob) {
        setTimeout(this.bob.bind(this), this._options.autoBobDelay);
      }
    }
  }, {
    key: "bob",
    value: function bob() {
      this._detach();
    }
  }, {
    key: "_createElement",
    value: function _createElement() {
      var element = createElement({
        className: [Popper._CLASS, this.constructor._CLASS],
        children: [this._createMain()]
      });

      if (!this._options.backdropDisabled) {
        this._createBackdrop(element);
      }

      return element;
    }
  }, {
    key: "_createBackdrop",
    value: function _createBackdrop(container) {
      var backdrop = new Backdrop({
        transparent: this._options.backdropTransparent,
        onClick: this._handleClickBackdrop.bind(this)
      });
      backdrop.attach(container);
    }
  }, {
    key: "_createMain",
    value: function _createMain() {
      return createElement({
        className: this.constructor._MAIN_CLASS,
        children: [this._createContent()]
      });
    }
  }, {
    key: "_createContent",
    value: function _createContent() {
      var options = {};

      if (this._options.content) {
        var content = this._options.content;

        if (content instanceof Node) {
          Object.assign(options, {
            children: [content]
          });
        } else {
          Object.assign(options, {
            properties: {
              textContent: content.toString()
            }
          });
        }
      }

      return createElement(_objectSpread({
        className: this.constructor._CONTENT_CLASS
      }, options));
    }
  }, {
    key: "_initTarget",
    value: function _initTarget() {
      var targetOption = this._options.target;
      var target;

      if (targetOption instanceof HTMLElement) {
        target = targetOption;
      } else if (typeof targetOption === 'string') {
        target = document.querySelector(targetOption);

        if (!target) {
          throw new Error("Cannot get an element with selector `".concat(targetOption, "`."));
        }
      } else {
        throw new Error("`options.target` must be `HTMLElement` or `string`, but got `".concat(targetOption, "`."));
      }

      this._target = target;

      this._listenTarget();
    }
  }, {
    key: "_attach",
    value: function _attach() {
      var parent = document.body;

      if (this._target) {
        parent = this._target.offsetParent;

        this._element.classList.add(this.constructor._POPS_WITH_TARGET_CLASS);

        this._setPosition();
      }

      parent.appendChild(this._element);
    }
  }, {
    key: "_detach",
    value: function _detach() {
      this._element.remove();
    }
  }, {
    key: "_handleClickBackdrop",
    value: function _handleClickBackdrop() {
      if (this._options.clicksBackdropToBob) {
        this.bob();
      }
    }
  }, {
    key: "_setPosition",
    value: function _setPosition() {
      var _this$_calcPosition = this._calcPosition(),
          left = _this$_calcPosition.left,
          top = _this$_calcPosition.top;

      this._element.style.cssText += ";\n            left: ".concat(left, "px;\n            top: ").concat(top, "px;\n        ");
    }
  }, {
    key: "_calcPosition",
    value: function _calcPosition() {
      var target = this._target;
      return {
        left: target.offsetLeft,
        top: target.offsetTop + target.offsetHeight
      };
    }
  }]);

  return Popper;
}();

_defineProperty(Popper, "_defaultOptions", {
  autoBob: false,
  autoBobDelay: 3000,
  backdropDisabled: false,
  backdropTransparent: false,
  clicksBackdropToBob: true,
  content: undefined,
  target: undefined
});

_defineProperty(Popper, "_CLASS", 'popper');

_defineProperty(Popper, "_POPPED_CLASS", 'popped');

_defineProperty(Popper, "_MAIN_CLASS", 'popper-main');

_defineProperty(Popper, "_CONTENT_CLASS", 'popper-content');

_defineProperty(Popper, "_POPS_WITH_TARGET_CLASS", 'popper-pops-with-target');

var Toast =
/*#__PURE__*/
function (_Popper) {
  _inherits(Toast, _Popper);

  function Toast(message, options) {
    _classCallCheck(this, Toast);

    return _possibleConstructorReturn(this, _getPrototypeOf(Toast).call(this, Object.assign({}, {
      content: message
    }, options)));
  }

  return Toast;
}(Popper);

_defineProperty(Toast, "_defaultOptions", {
  backdropDisabled: true,
  autoBob: true
});

_defineProperty(Toast, "_CLASS", 'toast');

var zh = {
  OK: '确定',
  CANCEL: '取消'
};

var en = {
  OK: 'OK',
  CANCEL: 'Cancel'
};

var i18n = {
  zh: zh,
  en: en
}[navigator.language.split('-')[0]];

var Dialog =
/*#__PURE__*/
function (_Popper) {
  _inherits(Dialog, _Popper);

  function Dialog(type, message, defaultValue) {
    var _context;

    var _this;

    _classCallCheck(this, Dialog);

    _this = _possibleConstructorReturn(this, _getPrototypeOf(Dialog).call(this, {
      content: message,
      type: type,
      defaultValue: defaultValue
    }));

    _defineProperty(_assertThisInitialized(_assertThisInitialized(_this)), "_value", '');

    _defineProperty(_assertThisInitialized(_assertThisInitialized(_this)), "_resolve", void 0);

    _defineProperty(_assertThisInitialized(_assertThisInitialized(_this)), "_reject", void 0);

    _this._handleKeydownOnBody = (_context = _this)._handleKeydownOnBody.bind(_context);

    if (_this._options.type === 'prompt') {
      _this._value = _this._options.defaultValue;
    }

    return _this;
  }

  _createClass(Dialog, [{
    key: "pop",
    value: function pop() {
      var _this2 = this;

      _get(_getPrototypeOf(Dialog.prototype), "pop", this).call(this);

      this._focus();

      document.body.addEventListener('keydown', this._handleKeydownOnBody);

      if (this._options.type === 'alert') {
        return;
      }

      return new Promise(function (resolve, reject) {
        _this2._resolve = resolve;
        _this2._reject = reject;
      });
    }
  }, {
    key: "bob",
    value: function bob() {
      _get(_getPrototypeOf(Dialog.prototype), "bob", this).call(this);

      document.body.removeEventListener('keydown', this._handleKeydownOnBody);
    }
  }, {
    key: "_createElement",
    value: function _createElement() {
      var element = _get(_getPrototypeOf(Dialog.prototype), "_createElement", this).call(this);

      element.classList.add(this._options.type);
      return element;
    }
  }, {
    key: "_createMain",
    value: function _createMain() {
      var element = _get(_getPrototypeOf(Dialog.prototype), "_createMain", this).call(this);

      if (this._options.type === 'prompt') {
        element.appendChild(this._createInput());
      }

      element.appendChild(this._createActions());
      return element;
    }
  }, {
    key: "_createInput",
    value: function _createInput() {
      var element = createElement({
        tagName: 'input',
        attributes: {
          value: this._options.defaultValue
        },
        className: this.constructor._INPUT_CLASS
      });
      element.addEventListener('input', this._handleInput.bind(this));
      element.addEventListener('keypress', this._handleKeypressOnInput.bind(this));
      return element;
    }
  }, {
    key: "_createActions",
    value: function _createActions() {
      var children = [this._createConfirmingTrigger()];

      if (this._options.type === 'confirm' || this._options.type === 'prompt') {
        children.push(this._createCancelingTrigger());
      }

      var element = createElement({
        className: this.constructor._ACTIONS_CLASS,
        children: children
      });
      element.addEventListener('click', this._handleActionsClick.bind(this));
      return element;
    }
  }, {
    key: "_createConfirmingTrigger",
    value: function _createConfirmingTrigger() {
      return createElement({
        tagName: 'button',
        attributes: {
          type: 'button'
        },
        properties: {
          textContent: this.constructor._CONFIRMING_TEXT
        },
        className: [this.constructor._ACTION_CLASS, this.constructor._CONFIRMING_CLASS]
      });
    }
  }, {
    key: "_createCancelingTrigger",
    value: function _createCancelingTrigger() {
      return createElement({
        tagName: 'button',
        attributes: {
          type: 'button'
        },
        properties: {
          textContent: this.constructor._CANCELING_TEXT
        },
        className: [this.constructor._ACTION_CLASS, this.constructor._CANCELING_CLASS]
      });
    }
  }, {
    key: "_handleActionsClick",
    value: function _handleActionsClick(e) {
      var target = e.target;

      if (target.classList.contains(this.constructor._CONFIRMING_CLASS)) {
        this._confirm();

        return;
      }

      if (target.classList.contains(this.constructor._CANCELING_CLASS)) {
        this._cancel();

        return;
      }
    }
  }, {
    key: "_handleKeydownOnBody",
    value: function _handleKeydownOnBody(e) {
      if (e.keyCode === 27) {
        this._cancel();

        return;
      }
    }
  }, {
    key: "_handleInput",
    value: function _handleInput(e) {
      this._value = e.target.value;
    }
  }, {
    key: "_handleKeypressOnInput",
    value: function _handleKeypressOnInput(e) {
      if (e.keyCode === 13) {
        this._confirm();

        return;
      }
    }
  }, {
    key: "_confirm",
    value: function _confirm() {
      switch (this._options.type) {
        case 'confirm':
          {
            this._resolve();

            break;
          }

        case 'prompt':
          {
            this._resolve(this._value);

            break;
          }
      }

      this.bob();
    }
  }, {
    key: "_cancel",
    value: function _cancel() {
      switch (this._options.type) {
        case 'confirm':
        case 'prompt':
          {
            this._reject();

            break;
          }
      }

      this.bob();
    }
  }, {
    key: "_focus",
    value: function _focus() {
      var element = this._element.querySelector(this._options.type === 'prompt' ? ".".concat(this.constructor._INPUT_CLASS) : ".".concat(this.constructor._CONFIRMING_CLASS));

      element.focus();
    }
  }]);

  return Dialog;
}(Popper);

_defineProperty(Dialog, "_defaultOptions", {
  clicksBackdropToBob: false,
  type: undefined,
  defaultValue: ''
});

_defineProperty(Dialog, "_CLASS", 'dialog');

_defineProperty(Dialog, "_MESSAGE_CLASS", 'dialog-message');

_defineProperty(Dialog, "_INPUT_CLASS", 'dialog-input');

_defineProperty(Dialog, "_ACTIONS_CLASS", 'dialog-actions');

_defineProperty(Dialog, "_ACTION_CLASS", 'dialog-action');

_defineProperty(Dialog, "_CONFIRMING_CLASS", 'dialog-action-confirm');

_defineProperty(Dialog, "_CANCELING_CLASS", 'dialog-action-cancel');

_defineProperty(Dialog, "_CONFIRMING_TEXT", i18n.OK);

_defineProperty(Dialog, "_CANCELING_TEXT", i18n.CANCEL);

var alert = function alert() {
  for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
    args[_key] = arguments[_key];
  }

  _construct(Dialog, ['alert'].concat(args)).pop();
};

var confirm = function confirm() {
  for (var _len2 = arguments.length, args = new Array(_len2), _key2 = 0; _key2 < _len2; _key2++) {
    args[_key2] = arguments[_key2];
  }

  return _construct(Dialog, ['confirm'].concat(args)).pop();
};

var prompt = function prompt() {
  for (var _len3 = arguments.length, args = new Array(_len3), _key3 = 0; _key3 < _len3; _key3++) {
    args[_key3] = arguments[_key3];
  }

  return _construct(Dialog, ['prompt'].concat(args)).pop();
};

var Notification =
/*#__PURE__*/
function (_Popper) {
  _inherits(Notification, _Popper);

  function Notification(message, options) {
    _classCallCheck(this, Notification);

    return _possibleConstructorReturn(this, _getPrototypeOf(Notification).call(this, Object.assign({}, {
      content: message
    }, options)));
  }

  return Notification;
}(Popper);

_defineProperty(Notification, "_defaultOptions", {
  backdropDisabled: true,
  autoBob: true
});

_defineProperty(Notification, "_CLASS", 'notification');

var Dropdown =
/*#__PURE__*/
function (_Popper) {
  _inherits(Dropdown, _Popper);

  function Dropdown(menu, target, options) {
    _classCallCheck(this, Dropdown);

    return _possibleConstructorReturn(this, _getPrototypeOf(Dropdown).call(this, Object.assign({}, {
      menu: menu,
      target: target
    }, options)));
  }

  _createClass(Dropdown, [{
    key: "_createContent",
    value: function _createContent() {
      return createElement({
        tagName: 'ul',
        className: this.constructor._MENU_CLASS,
        children: this._options.menu.map(this._createMenuItem.bind(this))
      });
    }
  }, {
    key: "_createMenuItem",
    value: function _createMenuItem(options) {
      var _this = this;

      var element = createElement({
        tagName: 'li',
        properties: {
          textContent: options.text
        },
        className: this.constructor._MENU_ITEM_CLASS
      });
      element.addEventListener('click', function () {
        options.handler();

        _this.bob();
      });
      return element;
    }
  }, {
    key: "_listenTarget",
    value: function _listenTarget() {
      this._target.addEventListener('click', this.pop.bind(this));
    }
  }]);

  return Dropdown;
}(Popper);

_defineProperty(Dropdown, "_defaultOptions", {
  backdropTransparent: true,
  menu: []
});

_defineProperty(Dropdown, "_CLASS", 'dropdown');

_defineProperty(Dropdown, "_MENU_CLASS", 'dropdown-menu');

_defineProperty(Dropdown, "_MENU_ITEM_CLASS", 'dropdown-menu-item');

exports.Toast = Toast;
exports.alert = alert;
exports.confirm = confirm;
exports.prompt = prompt;
exports.Notification = Notification;
exports.Dropdown = Dropdown;
