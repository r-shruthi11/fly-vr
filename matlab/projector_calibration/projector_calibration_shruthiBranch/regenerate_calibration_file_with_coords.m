clear; clc;


load('coords_left.mat')

% global h4 seth4
% 
% if isempty(seth4)
%     seth4 = 1;
%     disp('Setting h4');
%     h4=figure('OuterPosition',[10 10 684 608]);
% %         disp('ok?')
% end

h4=figure('OuterPosition',[10 10 684 608]);

h4 = generateDome_shruthi(screenRadius_,screenX_,screenY_,screenZ_, mirrorRadius_,mirrorX_,mirrorY_,mirrorZ_, projectorX_,projectorY_,projectorZ_, ...
    x0_,y0_,x1_,y1_,x2_,y2_,h4);

disp('Generated calibration file');

% close(h4);