app = angular.module(
  'kb', [
    'kb.controllers'
    'kb.directives'
    'kb.login'
    'ui.router'
    ])

app.config(($stateProvider, $urlRouterProvider) ->
  $urlRouterProvider.otherwise("/")

  $stateProvider
  .state("Loading", {
    url: "/"
    controller: ($state, Server) ->
      Server.poll().then( -> $state.go("board"))
    template: "<md-content>Loading ...<md-content>"
    })
  .state("board", {
    url: "/board"
    templateUrl: "kbBoard.html"
    })
  )

