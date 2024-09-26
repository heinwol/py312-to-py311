{
  description = "Script to convert syntax of python 3.11 to python 3.12.";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    devenv.url = "github:cachix/devenv";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ flake-parts, devenv, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        devenv.flakeModule
      ];
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin" ];
      perSystem = { config, self', inputs', pkgs, system, ... }:
        let
          poetry2nix = import inputs.poetry2nix { inherit pkgs; };
        in
        {

          devenv.shells = {
            default = {
              # packages = [ pkgs.poetry ];
              languages.python = {
                enable = true;
                package = pkgs.python312;
                poetry = {
                  enable = true;
                  activate.enable = true;
                  install.enable = true;
                };
              };
            };
          };
          # myPythonApp = poetry2nix.mkPoetryApplication { projectDir = ./.; };
        };
      flake = {
        # The usual flake attributes can be defined here, including system-
        # agnostic ones like nixosModule and system-enumerating ones, although
        # those are more easily expressed in perSystem.
      };
    };
}
