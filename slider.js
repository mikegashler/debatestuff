// -------------
// Slider widget
// -------------
function slider_mouse_down(id) {
	window.activeSliderId = id;
	return false;
}

function slider_mouse_up(e_event, b_watching) {
	if (window.activeSliderId != null) {
		var slider = window.active_sliders[window.activeSliderId];
		slider.set_value(slider.minValue + (slider.is_vertical
			? (slider.pathLength - parseInt(slider.el_slider.style.top) + slider.pathTop)
			: (parseInt(slider.el_slider.style.left) - slider.pathLeft)) / slider.pix2value);
		if (b_watching)	return;
		window.activeSliderId = null;
	}
	if (window.saved_mouse_up)
		return window.saved_mouse_up(e_event);
}

function drag_slider(e_event) {
    // check if in drag mode
	if (window.activeSliderId != null) {
		var slider = window.active_sliders[window.activeSliderId];
		var pxOffset;
		if (slider.is_vertical) {
			var sliderTop = window.mouseY - slider.sliderHeight / 2 - slider.get_abs_pos(1, 1) - 3;
			// limit the slider movement
			if (sliderTop < slider.pathTop)
				sliderTop = slider.pathTop;
			var pxMax = slider.pathTop + slider.pathLength;
			if (sliderTop > pxMax)
				sliderTop = pxMax;
			slider.el_slider.style.top = sliderTop + 'px';
			pxOffset = slider.pathLength - sliderTop + slider.pathTop;
		}
		else {
			var sliderLeft = window.mouseX - slider.sliderWidth / 2 - slider.get_abs_pos(0, 1) - 3;
			// limit the slider movement
			if (sliderLeft < slider.pathLeft)
				sliderLeft = slider.pathLeft;
			var pxMax = slider.pathLeft + slider.pathLength;
			if (sliderLeft > pxMax)
				sliderLeft = pxMax;
			slider.el_slider.style.left = sliderLeft + 'px';
			pxOffset = sliderLeft - slider.pathLeft;
		}
		slider_mouse_up(e_event, 1);
		return false;
	}
	if (window.saved_mouse_move)
		return window.saved_mouse_move(e_event);
}

function slider_mouse_move(e_event) {

	if (!e_event && window.event) e_event = window.event;

	// save mouse coordinates
	if (e_event) {
		window.mouseX = e_event.clientX + slider_filter_results (
			window.pageXOffset ? window.pageXOffset : 0,
			document.documentElement ? document.documentElement.scrollLeft : 0,
			document.body ? document.body.scrollLeft : 0
		);
		window.mouseY = e_event.clientY + slider_filter_results (
			window.pageYOffset ? window.pageYOffset : 0,
			document.documentElement ? document.documentElement.scrollTop : 0,
			document.body ? document.body.scrollTop : 0
		);
	}
    return drag_slider(e_event);
}

function slider_touch_move(e_event) {

	if (!e_event && window.event) e_event = window.event;

	// save touch coordinates
	if (e_event) {
		window.mouseX = e_event.changedTouches[0].pageX + slider_filter_results (
			window.pageXOffset ? window.pageXOffset : 0,
			document.documentElement ? document.documentElement.scrollLeft : 0,
			document.body ? document.body.scrollLeft : 0
		);
		window.mouseY = e_event.changedTouches[0].pageY + slider_filter_results (
			window.pageYOffset ? window.pageYOffset : 0,
			document.documentElement ? document.documentElement.scrollTop : 0,
			document.body ? document.body.scrollTop : 0
		);
	}
    return drag_slider(e_event);
}

function slider_filter_results(win, docel, body) {
	var result = win ? win : 0;
	if (docel && (!result || (result > docel)))
		result = docel;
	return body && (!result || (result > body)) ? body : result;
}

class Slider {
	constructor(bg_filename, bg_wid, bg_hgt, fg_filename, fg_wid, fg_hgt, initial_val, on_change) {
		// Register in a global collection
		if (!window.active_sliders)
			window.active_sliders = [];
		this.id = window.active_sliders.length;
		window.active_sliders[this.id] = this;

		this.is_vertical = false;
		this.sliderWidth = fg_wid;
		this.sliderHeight = fg_hgt;
		this.pathLeft = 1;
		this.pathTop = 1;
		this.pathLength = 300;
		this.minValue = 5;
		this.maxValue = 105;
		this.step = 5;
		this.zIndex = 1;

		this.pix2value = this.pathLength / (this.maxValue - this.minValue);
		if (this.value == null)
			this.value = this.minValue;

		// generate the control's HTML
		document.write(
			'<div style="width:' + bg_wid + 'px;height:' + bg_hgt + 'px;border:0; background-image:url(' + bg_filename + ')" id="sl' + this.id + 'base">' +
			'<img src="' + fg_filename + '" width="' + fg_wid + '" height="' + fg_hgt + '" border="0" style="position:relative;left:' + this.pathLeft + 'px;top:' + this.pathTop + 'px;z-index:' + this.zIndex + ';cursor:pointer;visibility:hidden;" name="sl' + this.id + 'slider" id="sl' + this.id + 'slider" onmousedown="return slider_mouse_down(' + this.id + ')" ontouchstart="return slider_mouse_down(' + this.id + ')"/></div>'
		);
		this.el_base = document.getElementById('sl' + this.id + 'base');
		this.el_slider = document.getElementById('sl' + this.id + 'slider');

		// Hook up document/window events
		if (!window.saved_mouse_move && document.onmousemove != slider_mouse_move) {
			window.saved_mouse_move = document.onmousemove;
			document.onmousemove = slider_mouse_move;
            document.ontouchmove = slider_touch_move;
		}
		if (!window.saved_mouse_up && document.onmouseup != slider_mouse_up) {
			window.saved_mouse_up = document.onmouseup;
			document.onmouseup = slider_mouse_up;
            document.ontouchend = slider_mouse_up;
		}
		this.on_change = on_change;
		this.value = initial_val - 1;
		this.set_value(initial_val);
		this.el_slider.style.visibility = 'visible';
	}

	set_value(value) {
		if (value == null)
			value = this.value == null ? this.minValue : this.value;
		if (isNaN(value))
			return;

		// Round to closest step
		if (this.step)
			value = Math.round((value - this.minValue) / this.step) * this.step + this.minValue;

		// Round away extreme decimals (like .00001 or .99999)
		if (value % 1)
			value = Math.round(value * 1e5) / 1e5;

		// Set the value
		value = Math.min(this.maxValue, Math.max(this.minValue, value));

		// Move the slider
		if (this.is_vertical)
			this.el_slider.style.top  = (this.pathTop + this.pathLength - Math.round((value - this.minValue) * this.pix2value)) + 'px';
		else
			this.el_slider.style.left = (this.pathLeft + Math.round((value - this.minValue) * this.pix2value)) + 'px';

		// Report the change
		if (this.value === value) return;
		this.value = value;
		if (this.on_change)
			this.on_change(this, value);
	}

	// get absolute position of the element in the document
	get_abs_pos(is_vertical, is_base) {
		var pos = 0,
			s_coord = (is_vertical ? 'Top' : 'Left');
		var el = is_base ? this.el_base : this.el_slider;
		var el_old = el;

		while (el) {
			pos += el["offset" + s_coord];
			el = el.offsetParent;
		}
		el = el_old;

		var offset;
		while (el.tagName != "BODY") {
			offset = el["scroll" + s_coord];
			if (offset)
				pos -= el["scroll" + s_coord];
			el = el.parentNode;
		}
		return pos;
	}
}
