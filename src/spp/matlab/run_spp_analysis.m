function run_spp_analysis(fname, opts)
% RUN_SPP_ANALYSIS  Run SPPplus (Fourier mode) on one CSV file.
%
%   run_spp_analysis(fname, Name=Value)
%
%   fname  Path to the data file WITHOUT the .csv extension. The CSV has no
%          header and four columns: time [s], strain, rate [1/s], stress [Pa].
%
%   Name-value options:
%     omega         Angular frequency [rad/s] (required, e.g. 2*pi*0.1)
%     M             Odd number of stress harmonics kept (default 7)
%     p             Whole number of cycles in the file (default 1)
%     strain_scale  Multiplier that converts strain to [-]; use 0.01 if the
%                   export gives strain in percent (default 1)
%     data_trunc    [1 first last] to keep only rows first..last
%                   (default [0 1 1] = no truncation)
%     save_figs     1 to save SPPplus figures as .jpg (default 0)
%
%   Requires the SPPplus v2 functions (SPPplus_read_v2, SPPplus_fourier_v2,
%   SPPplus_print_v2, SPPplus_figures_v2) on the MATLAB path.
%
%   Adapted from the SPPplus v2.1 run script by G. J. Donley and S. A. Rogers.
%   Please cite Rogers (2017) Rheol Acta 56:501-525 and
%   Donley et al. (2019) JNNFM when publishing results.

    arguments
        fname (1,1) string
        opts.omega (1,1) double {mustBePositive}
        opts.M (1,1) double {mustBeInteger, mustBePositive} = 7
        opts.p (1,1) double {mustBeInteger, mustBePositive} = 1
        opts.strain_scale (1,1) double {mustBePositive} = 1
        opts.data_trunc (1,3) double = [0 1 1]
        opts.save_figs (1,1) double = 0
    end

    if ~isfield(opts, 'omega')
        error('SPP:MissingOmega', 'omega (rad/s) must be given.');
    end
    if mod(opts.M, 2) ~= 1
        error('SPP:EvenHarmonics', 'M must be an odd integer (got %g).', opts.M);
    end
    if ~isfile(fname + ".csv")
        error('SPP:FileNotFound', 'The file %s.csv was not found.', fname);
    end

    ftype    = 2;                              % .csv input
    var_loc  = [1 2 3 4];                      % time, strain, rate, stress
    var_conv = [1 opts.strain_scale 1 1];      % unit conversions
    out_set  = [1 0 opts.save_figs];           % .txt output, no FS-frame file, figs

    [time_wave, resp_wave, L, fname_t] = SPPplus_read_v2(fname, ftype, ...
        var_loc, var_conv, opts.data_trunc);

    SPPplus_fourier_v2(time_wave, resp_wave, L, opts.omega, opts.M, opts.p, ...
        out_set, fname_t);
end
