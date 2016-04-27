L.Control.EasyButtons = L.Control.extend({
    options: {
        position: 'topright',
        title: '',
    },

    onAdd: function () {
        var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');

        this.link = L.DomUtil.create('a', 'leaflet-bar-part', container);
        this.__addImage()
        this.link.href = '#';

        L.DomEvent.on(this.link, 'click', this.__onClick, this);
        this.link.title = this.options.title;

        return container;
    },

    intendedFunction: function(){ alert('no function selected');},

    __onClick: function (e) {
        L.DomEvent.stopPropagation(e);
        L.DomEvent.preventDefault(e);
        this.intendedFunction();
        this.link.blur();
    },

    __addImage: function () {
        var icon = L.DomUtil.create('div', this.options.intendedIcon, this.link);
    }
});

L.easyButton = function( btnIcon , btnFunction , btnTitle , btnMap , btnId) {
    var newControl = new L.Control.EasyButtons();

    if (btnIcon) newControl.options.intendedIcon = btnIcon;
    if (btnId) newControl.options.id = btnId;

    if ( typeof btnFunction === 'function'){
	newControl.intendedFunction = btnFunction;
    }

    if (btnTitle) newControl.options.title = btnTitle;

    if ( btnMap === '' ){
    } else if ( btnMap ) {
	btnMap.addControl(newControl);
    } else {
	map.addControl(newControl);
    }
    return newControl;
};
