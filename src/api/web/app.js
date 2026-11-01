(function () {
  'use strict';

  var fallbackStorage = {};

  var App = {
    NAV: [
      { label: 'Ігри', href: 'games.html', roles: [] },
      { label: 'Календар', href: 'calendar.html', roles: ['player', 'master', 'owner'] },
      { label: 'Створити гру', href: 'create-game.html', roles: ['master', 'owner'] },
      { label: 'Сповіщення', href: 'notifications.html', roles: ['player', 'master', 'owner'] },
      { label: 'Профіль', href: 'profile.html', roles: ['player', 'master', 'owner'] },
      { label: 'Адміністрування', href: 'admin.html', roles: ['owner'] },
      { label: 'Вхід', href: 'login.html', roles: ['guest'] },
      { label: 'Реєстрація', href: 'register.html', roles: ['guest'] },
      { label: 'Вийти', action: 'logout', roles: ['player', 'master', 'owner'] }
    ],

    getSession: function () {
      try {
        var token = localStorage.getItem('access_token');
        var role = localStorage.getItem('user_role');
        if (token) {
          return { token: token, role: role || '' };
        }
      } catch (e) {
        if (fallbackStorage.access_token) {
          return { token: fallbackStorage.access_token, role: fallbackStorage.user_role || '' };
        }
      }
      return null;
    },

    saveSession: function (token, role) {
      try {
        localStorage.setItem('access_token', token);
        localStorage.setItem('user_role', role);
      } catch (e) {
        fallbackStorage.access_token = token;
        fallbackStorage.user_role = role;
      }
    },

    clearSession: function () {
      try {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_role');
      } catch (e) {
        delete fallbackStorage.access_token;
        delete fallbackStorage.user_role;
      }
      try {
        sessionStorage.removeItem('user_me');
      } catch (e) {}
    },

    getMe: async function () {
      var session = App.getSession();
      if (!session || !session.token) {
        return null;
      }
      try {
        var cached = sessionStorage.getItem('user_me');
        if (cached) {
          return JSON.parse(cached);
        }
      } catch (e) {}

      try {
        var user = await App.api('GET', '/users/me');
        if (user && user.id) {
          try {
            sessionStorage.setItem('user_me', JSON.stringify(user));
          } catch (e) {}
          return user;
        }
        return null;
      } catch (err) {
        return null;
      }
    },

    formatDateTime: function (isoString) {
      if (!isoString) return '';
      var date = new Date(isoString);
      if (isNaN(date.getTime())) return String(isoString);
      try {
        var formatter = new Intl.DateTimeFormat('uk-UA', {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        });
        return formatter.format(date);
      } catch (e) {
        return date.toLocaleString();
      }
    },

    formatSlot: function (startsAt, durationMinutes) {
      if (!startsAt) return '';
      var start = new Date(startsAt);
      if (isNaN(start.getTime())) return '';
      var duration = parseInt(durationMinutes, 10) || 0;
      var end = new Date(start.getTime() + duration * 60000);

      function pad(n) {
        return n < 10 ? '0' + n : String(n);
      }

      var startStr = pad(start.getHours()) + ':' + pad(start.getMinutes());
      var endStr = pad(end.getHours()) + ':' + pad(end.getMinutes());
      return startStr + '–' + endStr;
    },

    el: function (tag, attrs, children) {
      var elem = document.createElement(tag);
      if (attrs) {
        for (var key in attrs) {
          if (Object.prototype.hasOwnProperty.call(attrs, key)) {
            if (key.indexOf('on') === 0 && typeof attrs[key] === 'function') {
              elem.addEventListener(key.slice(2).toLowerCase(), attrs[key]);
            } else if (key === 'className') {
              elem.className = attrs[key];
            } else {
              elem.setAttribute(key, attrs[key]);
            }
          }
        }
      }
      if (children !== undefined && children !== null) {
        if (!Array.isArray(children)) {
          children = [children];
        }
        for (var i = 0; i < children.length; i++) {
          var child = children[i];
          if (child === null || child === undefined) continue;
          if (typeof child === 'string' || typeof child === 'number') {
            elem.appendChild(document.createTextNode(String(child)));
          } else if (child.nodeType) {
            elem.appendChild(child);
          }
        }
      }
      return elem;
    },

    api: async function (method, path, body) {
      var session = App.getSession();
      var headers = {};
      var options = {
        method: method,
        headers: headers
      };

      if (session && session.token) {
        headers['Authorization'] = 'Bearer ' + session.token;
      }

      if (body !== undefined && body !== null) {
        headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
      }

      var cleanPath = path.charAt(0) === '/' ? path : '/' + path;
      var response;
      try {
        response = await fetch('/api/v1' + cleanPath, options);
      } catch (networkErr) {
        var netError = new Error('Помилка мережі: ' + networkErr.message);
        netError.status = 0;
        netError.code = 'NETWORK_ERROR';
        throw netError;
      }

      if (response.status === 204) {
        return null;
      }

      var data = null;
      var contentType = response.headers.get('content-type');
      if (contentType && contentType.indexOf('application/json') !== -1) {
        try {
          data = await response.json();
        } catch (e) {
          data = null;
        }
      } else {
        try {
          var text = await response.text();
          if (text) data = JSON.parse(text);
        } catch (e) {
          data = null;
        }
      }

      if (!response.ok) {
        if (response.status === 401 && session && session.token) {
          App.clearSession();
          window.location.href = 'index.html';
        }

        var errCode = (data && data.error && data.error.code) || 'HTTP_' + response.status;
        var errMsg = (data && data.error && data.error.message) || response.statusText || 'Помилка запиту';
        var errDetails = (data && data.error && data.error.details) || [];
        var retryAfterHeader = response.headers.get('Retry-After');
        var retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : null;

        var err = new Error(errMsg);
        err.status = response.status;
        err.code = errCode;
        err.details = errDetails;
        err.retryAfter = retryAfter;
        throw err;
      }

      return data;
    },

    showError: function (err, container) {
      if (!container) return;
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }

      if (!err) {
        container.style.display = 'none';
        return;
      }

      container.style.display = 'block';
      var messageText = err.message || 'Виникла невідома помилка';
      if (err.status === 429 && err.retryAfter) {
        messageText += '. Спробуйте через ' + err.retryAfter + ' с';
      }

      var msgNode = document.createTextNode(messageText);
      container.appendChild(msgNode);

      if (err.details && Array.isArray(err.details) && err.details.length > 0) {
        var list = App.el('ul', { className: 'error-details' });
        for (var i = 0; i < err.details.length; i++) {
          var detail = err.details[i];
          var detailText = (detail.field ? detail.field + ': ' : '') + (detail.message || '');
          list.appendChild(App.el('li', {}, detailText));
        }
        container.appendChild(list);
      }
    },

    renderNav: function (container) {
      var navElem = container || document.getElementById('nav-container');
      if (!navElem) return;
      while (navElem.firstChild) {
        navElem.removeChild(navElem.firstChild);
      }

      var session = App.getSession();
      var currentRole = session ? session.role : null;
      var isGuest = !session;

      var currentPath = window.location.pathname;
      var currentPage = currentPath.substring(currentPath.lastIndexOf('/') + 1) || 'index.html';

      var ul = App.el('ul', { className: 'nav-list' });

      for (var i = 0; i < App.NAV.length; i++) {
        var item = App.NAV[i];
        var isVisible = false;

        if (!item.roles || item.roles.length === 0) {
          isVisible = true;
        } else if (item.roles.indexOf('guest') !== -1 && isGuest) {
          isVisible = true;
        } else if (currentRole && item.roles.indexOf(currentRole) !== -1) {
          isVisible = true;
        }

        if (!isVisible) continue;

        var li = App.el('li', { className: 'nav-item' });

        if (item.action === 'logout') {
          var btn = App.el('button', {
            type: 'button',
            className: 'nav-link nav-btn-logout',
            onclick: function () {
              App.clearSession();
              window.location.href = 'index.html';
            }
          }, item.label);
          li.appendChild(btn);
        } else {
          var linkClasses = 'nav-link';
          if (item.href === currentPage || (currentPage === 'index.html' && item.href === 'index.html')) {
            linkClasses += ' active';
          }
          var a = App.el('a', {
            href: item.href,
            className: linkClasses
          }, item.label);
          li.appendChild(a);
        }

        ul.appendChild(li);
      }

      navElem.appendChild(ul);
    }
  };

  window.App = App;
})();

