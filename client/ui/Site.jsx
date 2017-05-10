import React from 'react';

import Frame from 'Frame';
import SiteServer from '../model/site';

module.exports = class extends React.Component {

  constructor(props) {
    super(props);
    this.server = new SiteServer(this);
    this.state = this.server.model;
  };

  render() {
    return (
      <div>
        <Frame boards={this.state.boards}
               add_board={(name) => this.server.add_board(name)}
               />
        <h2>Site</h2>
      </div>
    );
  }

};
