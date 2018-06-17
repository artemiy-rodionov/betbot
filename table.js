var redraw_table = (function() {
  var data = null;
  var table = null;
  var redraw_counter = 0;

  function build_table(data, cb) {
    var table = $('<table class="display nowrap cell-border compact">');
    var thead = $('<thead>');
    var tfoot = $('<tfoot>');
    var head_row1 = $('<tr>');
    var head_row2 = $('<tr>');
    var foot_row = $('<tr>');
    head_row1.append('<th colspan="2">');
    head_row2.append('<th>&nbsp;</th>','<th>');
    foot_row.append('<th>&nbsp;</th>','<th>');
    var matches = data['matches'];
    for (var i = 0; i < matches.length; ++i) {
      var match_card = $('<th colspan="2">');
      match_card.append('<div>' + matches[i]['team0'] + '</div>');
      match_card.append('<div>' + matches[i]['result'] + '</div>');
      match_card.append('<div>' + matches[i]['team1'] + '</div>');
      head_row1.append(match_card);
      head_row2.append('<th>' + matches[i]['time'] + '</th>');
      head_row2.append('<th>' + matches[i]['round'] + '</th>');
      foot_row.append('<th>' + matches[i]['short_label'] + '</th>');
      foot_row.append('<th>' + matches[i]['round'] + '</th>');
    }
    thead.append(head_row1, head_row2);
    tfoot.append(foot_row);
    var tbody = $('<tbody>');
    var players = data['players'];
    for (var id in players) {
      var p = players[id];
      var tr = $('<tr>');
      tr.append('<th>' + p['name'] + (p['is_queen'] ? ' ♕' : '') + '</th>');
      tr.append('<th class="score"> ' + p['score'] + ' </th>');
      var predictions = p['predictions'];
      for (var i = 0; i < predictions.length; ++i) {
        var res = predictions[i]['result'];
        var score = predictions[i]['score'];
        tr.append('<th>' + ((res == null) ? '-' : res) + '</th>');
        tr.append('<th class="score">' + ((score == null) ? '' : score) + '</th>');
      }
      tbody.append(tr);
    }
    table.append(thead, tbody, tfoot);
    cb(table);
  }

  function draw_table(data, parent, id, height, cb) {
    build_table(data, function (table) {
      parent.addClass('hidden');
      parent.append(table);
      var draw_handled = false;
      var table_params = {
        paging: false,
        info: false,
        searching: false,
        scrollX: true,
        scrollY: height,
        scrollCollapse: true,
        order: [[1, 'desc']],
        fixedColumns: {
          leftColumns: 2
        }
      };
      table.attr('id', id);
      table.on('draw.dt', function() {
        if (!draw_handled) {
          draw_handled = true;
          window.setTimeout(function() {
            parent.find('.dataTables_scrollBody').scrollLeft(1000000000);
            parent.removeClass('hidden');
            cb(table);
          }, 500);
        }
      }).DataTable(table_params);
    });
  }

  function do_job() {
    var counter = ++redraw_counter;
    if (data == null) {
      $.getJSON('results.json', function(d) {
        data = d;
        do_job();
      });
      return;
    }
    $.LoadingOverlay("show", {
      background: "white"
    });
    var container = $('#container');
    var initial_height = 1000;
    var id = 'tmp_table_' + counter;
    draw_table(data, container, id, initial_height + 'px', function (t) {
      var diff = $('#' + id + '_wrapper').height() - initial_height;
      t.DataTable().destroy();
      t.remove();
      var body_margin = $('body').outerHeight(true) - $('body').height();
      var height = $(window).height() - diff - body_margin;
      draw_table(data, container, 'table_' + counter, height, function(t) {
        if (counter == redraw_counter) {
          if (table != null) {
            table.DataTable().destroy();
            table.remove();
            table = null;
          }
          table = t;
        } else {
          t.DataTable().destroy();
          t.remove();
        }
        $.LoadingOverlay("hide");
      });
    });
  };
  return do_job;
})();

$( window ).resize(redraw_table);
